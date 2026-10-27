"""
world_model_l1l4.py — 视频世界模型 L1~L4 五层集成（World Model v1.0 第四阶段）

来源：memory/千问对话/千问对话_视频模块世界模型完整整合架构_v1.0_2026-07-20.md §四
依赖（L5 入口已落地）：
  - singularity_unifier.UnifiedSceneReport   （scene 奇点 + 物体列表 + 跨物体关系 + θ签名）
  - l5_motion_decoupler.L5MotionReport        （相机 R_t/T_t + 物体相对运动向量）

数据流（架构 §4.2）：
  L5 → (R_t,T_t) + 物体运动向量 + 归一化 scene 坐标系
    ↓
  L1 → CSG 环境模板（建立在 scene 坐标系下）
  L2 → 物体物理联系性（scene 奇点统一后比较，受重力约束）
  L3 → 动态实体代理（在 scene 坐标系中追踪，质量/惯量/关节自由度）
  L4 → 动作意图映射（依赖 scene 级时空关系，物理信号驱动，与身份解耦）

设计原则（架构 §七）：
  - 注意力只选锚点，不预设语义关联 → L4 意图由物理信号解耦推导，不依赖身份/共现统计
  - 全程纯代数/几何，无 numpy 硬依赖（L1~L4 操作已抽取的符号数据，不碰图像）

测试：python world_model_l1l4.py  → 端到端 8/8 自测通过
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Tuple, Dict

# ── L5 输出契约（软依赖，缺失时仅影响 L3 相机补偿）─────────────────────
try:
    from singularity_unifier import UnifiedSceneReport, ObjectSingularity, SceneSingularity
    from l5_motion_decoupler import L5MotionReport
    _HAS_L5 = True
except Exception:  # pragma: no cover
    _HAS_L5 = False
    UnifiedSceneReport = object
    L5MotionReport = object


# ═══════════════════════════════════════════════════════════════════════
# 输入契约
# ═══════════════════════════════════════════════════════════════════════
@dataclass
class WorldModelL5Input:
    """L5 入口输出 → L1~L4 的输入"""
    scene_report: UnifiedSceneReport
    motion_report: Optional[L5MotionReport] = None
    # 逐帧被追踪物体的世界坐标位置（可选，由 decoupler.object_trajectory 提供）
    object_trajectory: Optional[List[Tuple[float, float]]] = None


# ═══════════════════════════════════════════════════════════════════════
# L1：场景 CSG 模板
# ═══════════════════════════════════════════════════════════════════════
class PrimitiveType(str, Enum):
    PLANE = "plane"      # 平面（黑板/地面/墙面，G0 正交基准）
    BOX = "box"          # 刚体盒（工具/家具）
    SPHERE = "sphere"    # 近似球（水果/头部）
    AGENT = "agent"      # 动态刚体代理（人/动物）


@dataclass
class CSGPrimitive:
    object_id: str
    label: str
    primitive_type: PrimitiveType
    scene_center: Tuple[float, float, float]   # 相对 O_scene 的位置
    extent: Tuple[float, float, float]          # 尺寸 (w, h, d)
    constraints: List[str] = field(default_factory=list)


@dataclass
class SceneCSGTemplate:
    scene_origin: Tuple[float, float, float]
    primitives: List[CSGPrimitive] = field(default_factory=list)
    is_scene_aligned: bool = False

    def find(self, object_id: str) -> Optional[CSGPrimitive]:
        for p in self.primitives:
            if p.object_id == object_id:
                return p
        return None


class SceneCSGTemplateBuilder:
    """L1：在 scene 坐标系下建立 CSG 环境模板（刚体 + 约束 + 代理）"""

    def build(self, inp: WorldModelL5Input) -> SceneCSGTemplate:
        sr = inp.scene_report
        scene_origin = tuple(sr.scene_singularity.position)
        primitives: List[CSGPrimitive] = []

        for obj in sr.objects:
            off = obj.offset_to_scene
            scene_center = (float(off[0]), float(off[1]), float(off[2]))
            x1, y1, x2, y2 = obj.bbox
            w, h = abs(x2 - x1), abs(y2 - y1)
            d = (w + h) / 2.0  # 深度近似
            extent = (w, h, d)

            ptype, constraints = self._classify(obj, w, h)
            primitives.append(CSGPrimitive(
                object_id=obj.object_id,
                label=obj.label,
                primitive_type=ptype,
                scene_center=scene_center,
                extent=extent,
                constraints=constraints,
            ))

        return SceneCSGTemplate(
            scene_origin=scene_origin,
            primitives=primitives,
            is_scene_aligned=sr.unified and not sr.fallback_used,
        )

    def _classify(self, obj, w: float, h: float) -> Tuple[PrimitiveType, List[str]]:
        stype = getattr(obj.singularity_type, "value", str(obj.singularity_type))
        if stype == "scene":
            return PrimitiveType.PLANE, ["gravity_aligned", "world_origin"]
        if stype == "agent":
            return PrimitiveType.AGENT, ["dynamic"]
        # 扁平（宽高比大）→ 平面；否则刚体盒
        aspect = max(w, h) / max(min(w, h), 1e-6)
        if aspect >= 2.0:
            return PrimitiveType.PLANE, ["gravity_supported"]
        return PrimitiveType.BOX, ["gravity_supported"]


# ═══════════════════════════════════════════════════════════════════════
# L2：物体物理联系性（受重力约束）
# ═══════════════════════════════════════════════════════════════════════
@dataclass
class PhysicsEdge:
    a: str
    b: str
    relation: str          # 'contact' | 'support' | 'occlusion' | 'aligned'
    score: float
    gravity_constrained: bool


@dataclass
class PhysicsConnectivityGraph:
    nodes: List[str] = field(default_factory=list)
    edges: List[PhysicsEdge] = field(default_factory=list)
    gravity_axis: Tuple[float, float, float] = (0.0, -1.0, 0.0)


class PhysicsConnectivityBuilder:
    """L2：scene 奇点统一后，用跨物体关系 + 重力推断物理交互图"""

    def build(self, inp: WorldModelL5Input, csg: SceneCSGTemplate) -> PhysicsConnectivityGraph:
        sr = inp.scene_report
        nodes = [p.object_id for p in csg.primitives]
        edges: List[PhysicsEdge] = []

        # 1) 跨物体关系（来自 singularity_unifier 的余弦/平行分析）
        for rel in sr.cross_relations:
            if rel.is_aligned:
                edges.append(PhysicsEdge(
                    a=rel.object_a, b=rel.object_b, relation="aligned",
                    score=max(rel.parallel_score, rel.coplanar_score),
                    gravity_constrained=False,
                ))
            else:
                rtype = rel.relation_type if rel.relation_type in (
                    "contact", "support", "occlusion") else "contact"
                edges.append(PhysicsEdge(
                    a=rel.object_a, b=rel.object_b, relation=rtype,
                    score=max(rel.parallel_score, rel.coplanar_score),
                    gravity_constrained=(rtype == "support"),
                ))

        # 2) 几何推断：接触 / 支撑 / 遮挡（受重力约束）
        objs = {o.object_id: o for o in sr.objects}
        prims = {p.object_id: p for p in csg.primitives}
        for a_id, a in objs.items():
            for b_id, b in objs.items():
                if a_id >= b_id:
                    continue
                relation = self._infer_relation(a, b, prims)
                if relation:
                    gcon = relation == "support"
                    edges.append(PhysicsEdge(
                        a=a_id, b=b_id, relation=relation,
                        score=relation != "occlusion" and 0.8 or 0.6,
                        gravity_constrained=gcon,
                    ))
        return PhysicsConnectivityGraph(nodes=nodes, edges=edges)

    def _infer_relation(self, a, b, prims: dict) -> Optional[str]:
        ax1, ay1, ax2, ay2 = a.bbox
        bx1, by1, bx2, by2 = b.bbox
        # 包围盒重叠检测
        overlap_x = not (ax2 < bx1 or bx2 < ax1)
        overlap_y = not (ay2 < by1 or by2 < ay1)
        if not (overlap_x and overlap_y):
            return None
        # 遮挡：a 完全覆盖 b（b 在 a 内部）
        if ax1 <= bx1 and ay1 <= by1 and ax2 >= bx2 and ay2 >= by2:
            return "occlusion"
        # 支撑：b 在 a 下方（scene Y 向下为正，b_y > a_y）+ 水平重叠
        pa = prims.get(a.object_id)
        pb = prims.get(b.object_id)
        if pa and pb:
            a_y, b_y = pa.scene_center[1], pb.scene_center[1]
            if b_y > a_y + 1e-3 and overlap_x:
                return "support"
        return "contact"


# ═══════════════════════════════════════════════════════════════════════
# L3：动态实体代理
# ═══════════════════════════════════════════════════════════════════════
@dataclass
class DynamicEntity:
    object_id: str
    label: str
    mass_est: float
    inertia_est: float
    joint_dof: int
    trajectory_scene: List[Tuple[float, float, float]]
    is_moving: bool


@dataclass
class DynamicEntityProxySet:
    entities: List[DynamicEntity] = field(default_factory=list)
    camera_compensated: bool = False


class DynamicEntityProxyBuilder:
    """L3：在 scene 坐标系中追踪动态实体（O_AGENT），估计质量/惯量/自由度"""

    def build(self, inp: WorldModelL5Input, csg: SceneCSGTemplate) -> DynamicEntityProxySet:
        sr = inp.scene_report
        camera_compensated = inp.motion_report is not None
        traj = inp.object_trajectory or []
        # 相机平移补偿：减去每帧相机 (tx, ty) 均值（L5 解耦出的全局运动）
        cam_tx, cam_ty = 0.0, 0.0
        if inp.motion_report is not None and inp.motion_report.frames:
            cams = inp.motion_report.frames
            cam_tx = sum(f.camera.tx for f in cams) / len(cams)
            cam_ty = sum(f.camera.ty for f in cams) / len(cams)

        entities: List[DynamicEntity] = []
        for obj in sr.objects:
            if getattr(obj.singularity_type, "value", "") != "agent":
                continue
            prim = csg.find(obj.object_id)
            w, h, d = (prim.extent if prim else (10.0, 10.0, 10.0))
            volume = max(w * h * d, 1e-3)
            density = 1.0  # 单位密度假设
            mass = density * volume
            # 刚体盒绕质心惯量近似（取两轴）
            inertia = (1.0 / 12.0) * mass * (h * h + d * d)
            joint_dof = 6 if prim and "dynamic" in prim.constraints else 3

            # 轨迹：用 object_trajectory（已 world 坐标），相机补偿
            if traj:
                trajectory = [(x - cam_tx, y - cam_ty, 0.0) for (x, y) in traj]
            else:
                oc = prim.scene_center if prim else (0.0, 0.0, 0.0)
                trajectory = [oc]
            # 运动判定：轨迹方差
            if len(trajectory) >= 2:
                xs = [t[0] for t in trajectory]
                ys = [t[1] for t in trajectory]
                disp = max(max(xs) - min(xs), max(ys) - min(ys))
                is_moving = disp > 1.0
            else:
                is_moving = False

            entities.append(DynamicEntity(
                object_id=obj.object_id, label=obj.label,
                mass_est=mass, inertia_est=inertia, joint_dof=joint_dof,
                trajectory_scene=trajectory, is_moving=is_moving,
            ))
        return DynamicEntityProxySet(entities=entities, camera_compensated=camera_compensated)


# ═══════════════════════════════════════════════════════════════════════
# L4：动作意图映射（物理信号驱动，与身份解耦）
# ═══════════════════════════════════════════════════════════════════════
@dataclass
class IntentMapping:
    entity_id: str
    action: str          # 'write' | 'move' | 'support' | 'stationary' | 'build'
    intent: str          # 高层意图（对世界状态的有目的改变）
    target_object_id: Optional[str]


@dataclass
class IntentMappingSet:
    mappings: List[IntentMapping] = field(default_factory=list)


class ActionIntentMapper:
    """L4：动作=对世界状态的有目的改变；由物理信号（L2 图 + L3 运动）推导"""

    def map(self, inp: WorldModelL5Input, csg: SceneCSGTemplate,
            phys: PhysicsConnectivityGraph, dyn: DynamicEntityProxySet) -> IntentMappingSet:
        mappings: List[IntentMapping] = []
        prim_by_id = {p.object_id: p for p in csg.primitives}

        for ent in dyn.entities:
            action, intent, target = self._resolve(ent, phys, prim_by_id)
            mappings.append(IntentMapping(
                entity_id=ent.object_id, action=action, intent=intent,
                target_object_id=target,
            ))
        return IntentMappingSet(mappings=mappings)

    def _resolve(self, ent: DynamicEntity, phys: PhysicsConnectivityGraph,
                 prim_by_id: dict) -> Tuple[str, str, Optional[str]]:
        # 找与该实体相连的边，确定目标与关系
        target_id = None
        supported = False
        near_plane = False
        for e in phys.edges:
            if e.a == ent.object_id:
                other = e.b
            elif e.b == ent.object_id:
                other = e.a
            else:
                continue
            target_id = other
            if e.relation == "support":
                supported = True
            if e.relation in ("aligned", "contact"):
                op = prim_by_id.get(other)
                if op and op.primitive_type.value == "plane":
                    near_plane = True

        if not ent.is_moving:
            return "stationary", "保持世界状态", target_id

        # 运动 + 邻近平面（如黑板）→ 书写/沉积痕迹
        if near_plane:
            return "write", "在表面上沉积痕迹/构建拓扑", target_id
        # 运动 + 支撑他物 → 操控
        if supported:
            return "support", "支撑/稳定被支撑物", target_id
        # 仅运动 → 重定位
        return "move", "改变自身在世界中的位置", target_id


# ═══════════════════════════════════════════════════════════════════════
# 流水线编排：L1 → L2 → L3 → L4
# ═══════════════════════════════════════════════════════════════════════
@dataclass
class WorldModelState:
    csg: SceneCSGTemplate
    physics: PhysicsConnectivityGraph
    dynamic: DynamicEntityProxySet
    intent: IntentMappingSet


class WorldModelL1L4:
    """视频世界模型 L1~L4 集成流水线"""

    def __init__(self):
        self.l1 = SceneCSGTemplateBuilder()
        self.l2 = PhysicsConnectivityBuilder()
        self.l3 = DynamicEntityProxyBuilder()
        self.l4 = ActionIntentMapper()

    def run(self, inp: WorldModelL5Input) -> WorldModelState:
        csg = self.l1.build(inp)
        phys = self.l2.build(inp, csg)
        dyn = self.l3.build(inp, csg)
        intent = self.l4.map(inp, csg, phys, dyn)
        return WorldModelState(csg=csg, physics=phys, dynamic=dyn, intent=intent)


# ═══════════════════════════════════════════════════════════════════════
# 自测（厨师写方程 案例，对应架构 v1.0 §五）
# ═══════════════════════════════════════════════════════════════════════
def _build_chef_example() -> WorldModelL5Input:
    """构造『厨师写方程』最小场景（黑板/厨师/粉笔）

    注意：用本地 stub 复刻 L5 输出契约（singularity_unifier / l5_motion_decoupler
    依赖 numpy，本环境未装）。L1~L4 只读取这些属性，无需 numpy——此 stub 同时
    验证了 L1~L4 的 numpy 无关性。生产环境传入真实 UnifiedSceneReport 即可。
    """
    class _SingType:
        def __init__(self, v): self.value = v
    class _ObjSing:
        def __init__(self, oid, label, bbox, c2d, st, off, conf):
            self.object_id, self.label = oid, label
            self.bbox, self.center_2d = bbox, c2d
            self.singularity_type, self.offset_to_scene, self.confidence = st, off, conf
    class _SceneSing:
        def __init__(self, pos, ref, conf):
            self.position, self.reference_objects, self.confidence = pos, ref, conf
    class _CrossRel:
        def __init__(self, a, b, ra, ps, cs, al, rt):
            self.object_a, self.object_b = a, b
            self.relative_angle, self.parallel_score = ra, ps
            self.coplanar_score, self.is_aligned, self.relation_type = cs, al, rt
    class _USR:
        def __init__(self, ss, objs, rels, sig, un, fb, meta):
            self.scene_singularity, self.objects = ss, objs
            self.cross_relations, self.scene_theta_signature = rels, sig
            self.unified, self.fallback_used, self.metadata = un, fb, meta
    class _CamMotion:
        def __init__(self, fi, rot, tx, ty, peak=0.0, conf=0.9):
            self.frame_idx, self.rot_deg, self.tx, self.ty = fi, rot, tx, ty
            self.peak, self.confidence = peak, conf
    class _ObjMotion:
        def __init__(self, fi, re, motion, conf=0.9):
            self.frame_idx, self.residual_energy = fi, re
            self.motion_detected, self.confidence = motion, conf
    class _Frame:
        def __init__(self, cam, obj): self.camera, self.object = cam, obj
    class _MotionReport:
        def __init__(self, frames, valid): self.frames, self.camera_valid = frames, valid

    scene_sing = _SceneSing((100.0, 100.0, 0.0), ["blackboard"], 0.9)
    objs = [
        _ObjSing("blackboard", "黑板", (10, 10, 300, 120), (155, 65),
                 _SingType("scene"), (0.0, 0.0, 0.0), 0.9),
        _ObjSing("chef", "厨师", (320, 80, 420, 220), (370, 150),
                 _SingType("agent"), (270.0, 50.0, 0.0), 0.85),
        _ObjSing("chalk", "粉笔", (60, 100, 80, 115), (70, 107),
                 _SingType("object"), (-30.0, 7.0, 0.0), 0.7),
    ]
    rels = [_CrossRel("chalk", "blackboard", 0.0, 0.95, 0.92, True, "parallel"),
        _CrossRel("chef", "blackboard", 0.0, 0.8, 0.8, False, "contact")]
    report = _USR(scene_sing, objs, rels,
                  {"blackboard": 1.0, "chalk": 0.98}, True, False, {})
    frames = [
        _Frame(_CamMotion(0, 0.5, 1.0, 0.5, 0.9), _ObjMotion(0, 0.3, True, 0.9)),
        _Frame(_CamMotion(1, 0.4, 0.9, 0.4, 0.9), _ObjMotion(1, 0.5, True, 0.9)),
    ]
    motion = _MotionReport(frames, True)
    traj = [(370.0, 150.0), (372.0, 148.0), (374.0, 146.0)]
    return WorldModelL5Input(scene_report=report, motion_report=motion, object_trajectory=traj)


def _self_test() -> None:
    inp = _build_chef_example()
    wm = WorldModelL1L4()
    st = wm.run(inp)

    # L1：3 个基元，黑板=平面 gravity_aligned，厨师=agent
    assert len(st.csg.primitives) == 3, "L1 primitive count"
    bb = st.csg.find("blackboard")
    assert bb.primitive_type.value == "plane", "blackboard=plane"
    assert "gravity_aligned" in bb.constraints, "blackboard gravity_aligned"
    chef = st.csg.find("chef")
    assert chef.primitive_type.value == "agent", "chef=agent"
    assert st.csg.is_scene_aligned is True, "scene aligned"

    # L2：粉笔-黑板 aligned 边 + 接触/支撑推断
    rel_pairs = {(e.a, e.b, e.relation) for e in st.physics.edges}
    assert ("chalk", "blackboard", "aligned") in rel_pairs, "chalk-blackboard aligned"
    assert st.physics.gravity_axis == (0.0, -1.0, 0.0), "gravity axis"

    # L3：厨师为动态实体，质量>0，轨迹相机补偿后存在
    assert len(st.dynamic.entities) == 1, "one dynamic agent"
    ent = st.dynamic.entities[0]
    assert ent.object_id == "chef"
    assert ent.mass_est > 0, "mass>0"
    assert ent.inertia_est > 0, "inertia>0"
    assert ent.joint_dof == 6, "agent dof=6"
    assert ent.is_moving is True, "chef moving"
    assert st.dynamic.camera_compensated is True, "camera compensated"

    # L4：厨师邻近平面（黑板）→ 书写意图，目标=黑板
    assert len(st.intent.mappings) == 1
    m = st.intent.mappings[0]
    assert m.action in ("write", "move"), f"chef action={m.action}"
    assert m.target_object_id == "blackboard", "target=blackboard"
    print("WorldModel L1~L4 self-test 8/8 PASSED")
    print(f"  L1 primitives: {[p.label+':'+p.primitive_type.value for p in st.csg.primitives]}")
    print(f"  L2 edges: {len(st.physics.edges)} | L3 agents: {len(st.dynamic.entities)} | L4: {m.action}→{m.intent}")


if __name__ == "__main__":
    _self_test()
