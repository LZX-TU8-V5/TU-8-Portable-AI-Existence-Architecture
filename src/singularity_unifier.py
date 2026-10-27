# -*- coding: utf-8 -*-
"""
singularity_unifier.py — L5 视觉模块三维奇点统一

来源：视觉模块L5入口剩余任务#9
目标：统一多物体场景下的奇点基准，使跨物体余弦校验成为可能

核心问题：
  单一物体余弦校验参考自身几何中心(O_object)
  scene级校验参考世界原点(O_scene)
  两个奇点不同 → 直接比较S(θ)毫无意义

解决方案：
  注意力机制识别每个物体锚定的奇点类型
  计算偏移向量 Δ_O = O_scene - O_object
  将所有物体校正到统一scene奇点
  scene级余弦校验才有效

奇点类型：
  O_SCENE  : 世界坐标系原点（墙角/地面标记/建筑角）
  O_OBJECT : 物体自身几何中心
  O_AGENT  : 动态物体重心（运动中）

接口：
  SingularityUnifier.unify(detected_objects) -> UnifiedSceneReport
  .classify_object(bbox, label) -> SingularityType
  .compute_offset(object_center, singularity_type) -> np.ndarray
  .verify_scene(s_A_scene, s_B_scene) -> CrossObjectRelation
"""

import sys
from pathlib import Path
sys.path.insert(0, r'C:\Users\qq366410837\.qclaw\workspace\src')

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Literal
from enum import Enum


# ─────────────────────────────────────────────────────────────────────────────
# 数据结构
# ─────────────────────────────────────────────────────────────────────────────

class SingularityType(Enum):
    """奇点类型枚举"""
    O_SCENE = "scene"    # 世界坐标系原点（墙角/地面标记）
    O_OBJECT = "object"  # 物体自身几何中心
    O_AGENT = "agent"    # 动态物体重心
    O_UNKNOWN = "unknown"


@dataclass
class ObjectSingularity:
    """单个物体的奇点信息"""
    object_id: str
    label: str
    bbox: tuple[float, float, float, float]   # (x1, y1, x2, y2) 像素坐标
    center_2d: tuple[float, float]            # (cx, cy) 像素坐标
    singularity_type: SingularityType
    offset_to_scene: tuple[float, float, float]  # (Δx, Δy, Δz) scene偏移
    confidence: float                         # 奇点分类置信度

    def __repr__(self):
        return (f"ObjectSingularity({self.label}, {self.singularity_type.value}, "
                f"offset=({self.offset_to_scene[0]:.1f},{self.offset_to_scene[1]:.1f}))")


@dataclass
class SceneSingularity:
    """场景级世界奇点"""
    position: tuple[float, float, float]     # O_scene在像素坐标系中的位置
    reference_objects: list[str]              # 用于确定世界原点的参考物体ID
    confidence: float                        # 确定置信度


@dataclass
class CrossObjectRelation:
    """跨物体关系（scene坐标系下）"""
    object_a: str
    object_b: str
    relative_angle: Optional[float]           # B相对于A的角度差（°）
    parallel_score: float                   # 平行度 ∈ [0,1]
    coplanar_score: float                   # 共面度 ∈ [0,1]
    is_aligned: bool                        # 是否对齐（平行且共面）
    relation_type: str                      # 'parallel' | 'perpendicular' | 'oblique' | 'unknown'


@dataclass
class UnifiedSceneReport:
    """统一场景报告"""
    scene_singularity: SceneSingularity
    objects: list[ObjectSingularity]
    cross_relations: list[CrossObjectRelation]
    scene_theta_signature: dict              # scene级余弦签名 {object_id: S_scene(θ)}
    unified: bool                           # 是否成功统一
    fallback_used: bool                      # 是否使用了降级（无法确定O_scene时）
    metadata: dict


# ─────────────────────────────────────────────────────────────────────────────
# 奇点检测器
# ─────────────────────────────────────────────────────────────────────────────

class SingularityDetector:
    """
    检测给定物体所属的奇点类型。

    策略：
    - 世界级参考物（墙角/地面/建筑角）→ O_SCENE
    - 静态物体（桌面/椅子/书本）→ O_OBJECT
    - 动态/运动物体（人/动物/车辆）→ O_AGENT
    - 低置信时回退到 O_OBJECT（最常见情况）
    """

    # 关键词映射：世界级参考物
    SCENE_KEYWORDS = {
        'wall', 'floor', 'ground', 'ceiling',       # 建筑结构
        'corner', 'junction', 'intersection',         # 接合部
        'door', 'window', 'frame',                   # 门窗框
        'building', 'room', 'space',                 # 空间标记
        'grid', 'tile', 'board',                    # 规则网格（暗示绝对坐标系）
        'wall_corner', 'floor_edge',                # 边界
        '墙壁', '地面', '墙角', '天花板',           # 中文
    }

    # 动态物体关键词
    AGENT_KEYWORDS = {
        'person', 'human', 'man', 'woman', 'child',  # 人
        'animal', 'dog', 'cat', 'bird',              # 动物
        'car', 'bike', 'motorcycle', 'bus',          # 车辆
        'robot', 'drone',                           # 机械体
        'moving', 'walking', 'running', 'falling',   # 运动状态
        '人', '动物', '车', '移动',                 # 中文
    }

    # 高大垂直物体（通常是场景参照物）
    STRUCTURAL_KEYWORDS = {
        'wall', 'door', 'window', 'pillar', 'column',
        'building', 'corner', 'pillar', 'post',
        '墙壁', '门', '窗', '柱', '建筑',
    }

    def classify(self, label: str, bbox: tuple[float, float, float, float],
                motion_detected: bool = False) -> tuple[SingularityType, float]:
        """
        分类物体所属奇点类型。

        Args:
            label: 物体标签（字符串）
            bbox: (x1, y1, x2, y2) 像素边界框
            motion_detected: 是否有运动检测信号

        Returns:
            (singularity_type, confidence)
        """
        label_lower = label.lower()
        x1, y1, x2, y2 = bbox
        width = x2 - x1
        height = y2 - y1
        aspect = height / (width + 1e-9)
        area = width * height

        # ── 规则1：运动物体 → O_AGENT ─────────────────────────────
        if motion_detected and any(kw in label_lower for kw in self.AGENT_KEYWORDS):
            return SingularityType.O_AGENT, 0.9

        # ── 规则2：世界级参考物 → O_SCENE ───────────────────────
        if any(kw in label_lower for kw in self.SCENE_KEYWORDS):
            return SingularityType.O_SCENE, 0.85

        # ── 规则3：高大垂直结构 → O_SCENE（可能是墙壁/柱子）────
        if aspect > 2.0 and height > 200 and any(kw in label_lower for kw in self.STRUCTURAL_KEYWORDS):
            return SingularityType.O_SCENE, 0.75

        # ── 规则4：大面积低矮物体（地面/桌面）→ O_SCENE ───────
        if aspect < 0.3 and area > 10000:
            return SingularityType.O_SCENE, 0.7

        # ── 规则5：运动物体（无运动检测但名称暗示）→ O_AGENT
        if any(kw in label_lower for kw in self.AGENT_KEYWORDS):
            return SingularityType.O_AGENT, 0.7

        # ── 默认：静态物体 → O_OBJECT ───────────────────────────
        return SingularityType.O_OBJECT, 0.6

    def find_scene_reference(self, objects: list[ObjectSingularity]) -> Optional[SceneSingularity]:
        """
        从物体列表中寻找场景级世界原点参考。

        策略：
        1. 找面积最大且aspect最低的物体 → 地面/桌面 → 取其最左下角作为O_scene
        2. 找两个高大垂直物体 → 墙角 → 取交点作为O_scene
        3. 找最靠近图像四角的物体 → 墙角
        4. 回退：取最小x+y的物体左下角
        """
        if not objects:
            return None

        scene_objs = [o for o in objects if o.singularity_type == SingularityType.O_SCENE]

        # 策略1：最大低矮物体
        candidates = [o for o in objects
                     if o.singularity_type == SingularityType.O_SCENE]
        if candidates:
            # 选面积最大的
            best = max(candidates, key=lambda o: (o.bbox[2]-o.bbox[0])*(o.bbox[3]-o.bbox[1]))
            x1, y1, x2, y2 = best.bbox
            # 世界原点 = 该物体左下角（像素坐标系）
            return SceneSingularity(
                position=(x1, y2, 0.0),
                reference_objects=[best.object_id],
                confidence=best.confidence,
            )

        # 策略2：两个高大垂直物体 → 墙角
        tall = [o for o in objects
               if (o.bbox[3]-o.bbox[1])/(o.bbox[2]-o.bbox[0]+1e-9) > 1.5
               and (o.bbox[3]-o.bbox[1]) > 150]
        if len(tall) >= 2:
            # 选最左和最下的组合 → 墙角
            leftmost = min(tall, key=lambda o: o.center_2d[0])
            bottommost = min(tall, key=lambda o: o.center_2d[1])
            cx = leftmost.bbox[2]  # 左物体右边线
            cy = bottommost.bbox[3]  # 下物体底边线
            return SceneSingularity(
                position=(cx, cy, 0.0),
                reference_objects=[leftmost.object_id, bottommost.object_id],
                confidence=min(leftmost.confidence, bottommost.confidence) * 0.9,
            )

        # 策略3：最靠近图像左下角的物体
        h, w = 480, 640  # 默认图像尺寸
        closest = min(objects, key=lambda o: (o.center_2d[0]**2 + (h - o.center_2d[1])**2))
        x1, y1, x2, y2 = closest.bbox
        return SceneSingularity(
            position=(x1, y2, 0.0),
            reference_objects=[closest.object_id],
            confidence=closest.confidence * 0.5,
        )


# ─────────────────────────────────────────────────────────────────────────────
# 偏移向量计算器
# ─────────────────────────────────────────────────────────────────────────────

class OffsetComputer:
    """
    计算物体奇点到场景奇点的偏移向量。

    像素坐标系 → 世界坐标系的映射（简化版）：
      世界原点 O_scene 在像素中 = (O_scene_x, O_scene_y)
      物体中心在像素中 = (cx, cy)
      偏移向量 Δ = (O_scene_x - cx, O_scene_y - cy, 0)

    真实场景需要相机内参和外参（此处为简化投影）
    """

    def __init__(self, focal_length: float = 500.0, sensor_width: float = 36.0):
        """
        Args:
            focal_length: 焦距（像素）
            sensor_width: 传感器宽度（mm）
        """
        self.focal_length = focal_length
        self.sensor_width = sensor_width

    def compute_offset(
        self,
        object_center: tuple[float, float],
        singularity_type: SingularityType,
        scene_origin: tuple[float, float, float],
        depth_z: float = 1.0,  # 物体深度（米），默认1m
    ) -> tuple[float, float, float]:
        """
        计算物体到场景原点的偏移向量。

        Returns:
            (Δx, Δy, Δz) 世界坐标系偏移（米）
        """
        cx, cy = object_center
        O_x, O_y, O_z = scene_origin

        # 像素差 → 世界坐标（简化针孔相机模型）
        # Δpixel_x = (cx - O_x) → Δworld_x = (cx - O_x) * depth_z / focal_length
        scale = depth_z / self.focal_length
        dx = (cx - O_x) * scale
        dy = (cy - O_y) * scale
        dz = depth_z

        return (round(dx, 4), round(dy, 4), round(dz, 4))

    def correct_to_scene(
        self,
        s_object: float,
        theta_object: float,
        offset: tuple[float, float, float],
        depth_z: float = 1.0,
    ) -> float:
        """
        将物体自身余弦签名校正到scene坐标系。

        简化模型：
          S_scene(θ) = S_object(θ) · (1 + α · |Δ|)
          其中 α 是经验系数（偏移越大，scene级签名偏差越大）

        更精确的模型需要相机外参，这里用简化版。
        """
        dx, dy, dz = offset
        dist = np.sqrt(dx**2 + dy**2 + dz**2 + 1e-9)
        # 经验系数：距离每增加0.5m，scene签名偏差约5%
        alpha = 0.1 / 0.5
        correction = 1.0 + alpha * dist
        return s_object * correction


# ─────────────────────────────────────────────────────────────────────────────
# 跨物体关系分析器
# ─────────────────────────────────────────────────────────────────────────────

class CrossObjectAnalyzer:
    """
    在scene坐标系下分析跨物体关系。

    关键：只有在统一到scene奇点后，才能比较不同物体的余弦签名。
    """

    ANGLE_TOLERANCE_PARALLEL = 5.0    # 平行判定容差（°）
    ANGLE_TOLERANCE_COPLANAR = 10.0   # 共面判定容差（°）

    def analyze_relation(
        self,
        theta_a: float,
        theta_b: float,
        s_a: float,
        s_b: float,
    ) -> CrossObjectRelation:
        """
        分析两个物体在scene坐标系下的关系。

        Args:
            theta_a, theta_b: scene坐标系下的角度（°）
            s_a, s_b: scene坐标系下的余弦签名值
        """
        # 相对角度
        rel_angle = abs(theta_a - theta_b) % 180
        if rel_angle > 90:
            rel_angle = 180 - rel_angle

        # 平行度（角度差越小越平行）
        parallel_score = max(0.0, 1.0 - rel_angle / self.ANGLE_TOLERANCE_PARALLEL)

        # 共面度（余弦签名比值）
        if min(s_a, s_b) > 1e-6:
            coplanar_score = min(s_a, s_b) / max(s_a, s_b)
        else:
            coplanar_score = 0.0

        # 对齐判定
        is_aligned = parallel_score > 0.7 and coplanar_score > 0.6

        # 关系类型
        if rel_angle < self.ANGLE_TOLERANCE_PARALLEL:
            rel_type = 'parallel'
        elif abs(rel_angle - 90) < self.ANGLE_TOLERANCE_PARALLEL:
            rel_type = 'perpendicular'
        else:
            rel_type = 'oblique'

        return CrossObjectRelation(
            object_a='',
            object_b='',
            relative_angle=round(rel_angle, 2),
            parallel_score=round(parallel_score, 3),
            coplanar_score=round(coplanar_score, 3),
            is_aligned=is_aligned,
            relation_type=rel_type,
        )


# ─────────────────────────────────────────────────────────────────────────────
# 奇点统一器（主接口）
# ─────────────────────────────────────────────────────────────────────────────

class SingularityUnifier:
    """
    三维奇点统一器。

    使用流程：
      unifier = SingularityUnifier()
      report = unifier.unify(detected_objects)  # list of (label, bbox, motion)
      for obj in report.objects:
          print(f"{obj.label}: {obj.singularity_type.value}, offset={obj.offset_to_scene}")
      for rel in report.cross_relations:
          print(f"{rel.object_a}  <->  {rel.object_b}: {rel.relation_type}")
    """

    def __init__(self, focal_length: float = 500.0):
        self.detector = SingularityDetector()
        self.offset_computer = OffsetComputer(focal_length=focal_length)
        self.analyzer = CrossObjectAnalyzer()
        self._last_scene_singularity: Optional[SceneSingularity] = None

    def classify_object(
        self,
        label: str,
        bbox: tuple[float, float, float, float],
        motion_detected: bool = False,
    ) -> tuple[SingularityType, float]:
        """分类单个物体奇点类型"""
        return self.detector.classify(label, bbox, motion_detected)

    def compute_offset(
        self,
        object_center: tuple[float, float],
        singularity_type: SingularityType,
        depth_z: float = 1.0,
    ) -> tuple[float, float, float]:
        """计算偏移向量"""
        if self._last_scene_singularity is None:
            return (0.0, 0.0, 0.0)
        return self.offset_computer.compute_offset(
            object_center, singularity_type,
            self._last_scene_singularity.position, depth_z,
        )

    def verify_scene(
        self,
        theta_a: float, s_a: float,
        theta_b: float, s_b: float,
    ) -> CrossObjectRelation:
        """scene级余弦校验"""
        return self.analyzer.analyze_relation(theta_a, s_a, theta_b, s_b)

    def unify(
        self,
        detections: list[dict],
        img_size: tuple[int, int] = (480, 640),
    ) -> UnifiedSceneReport:
        """
        统一场景奇点。

        Args:
            detections: list of {label, bbox, motion, theta_object, s_object}
                - label: str，物体标签
                - bbox: (x1, y1, x2, y2)，像素边界框
                - motion: bool，是否有运动
                - theta_object: float，物体自身坐标系下的角度（°）
                - s_object: float，物体自身余弦签名值

        Returns:
            UnifiedSceneReport
        """
        h, w = img_size
        objects = []

        # Step 1: 分类每个物体的奇点类型
        for i, det in enumerate(detections):
            label = det.get('label', 'unknown')
            bbox = det.get('bbox', (0, 0, 0, 0))
            motion = det.get('motion', False)
            x1, y1, x2, y2 = bbox
            cx, cy = ((x1 + x2) / 2, (y1 + y2) / 2)

            s_type, conf = self.detector.classify(label, bbox, motion)
            objects.append(ObjectSingularity(
                object_id=f"obj_{i}",
                label=label,
                bbox=bbox,
                center_2d=(cx, cy),
                singularity_type=s_type,
                offset_to_scene=(0.0, 0.0, 0.0),  # 暂定，后更新
                confidence=conf,
            ))

        # Step 2: 寻找场景世界原点
        scene_singularity = self.detector.find_scene_reference(objects)
        fallback_used = scene_singularity is None

        if scene_singularity is None:
            # 降级：取图像左下角作为scene原点
            scene_singularity = SceneSingularity(
                position=(0.0, float(h), 0.0),
                reference_objects=[],
                confidence=0.3,
            )

        self._last_scene_singularity = scene_singularity

        # Step 3: 计算每个物体的偏移向量
        for obj in objects:
            if obj.singularity_type == SingularityType.O_SCENE:
                # 世界级物体本身是scene原点，偏移为0
                obj.offset_to_scene = (0.0, 0.0, 0.0)
            else:
                obj.offset_to_scene = self.offset_computer.compute_offset(
                    obj.center_2d, obj.singularity_type,
                    scene_singularity.position,
                )

        # Step 4: 跨物体关系分析
        cross_relations = []
        non_scene_objects = [o for o in objects if o.singularity_type != SingularityType.O_SCENE]

        for i in range(len(non_scene_objects)):
            for j in range(i + 1, len(non_scene_objects)):
                oa = non_scene_objects[i]
                ob = non_scene_objects[j]

                det_a = next((d for d in detections if d.get('label') == oa.label), None)
                det_b = next((d for d in detections if d.get('label') == ob.label), None)

                if det_a and det_b:
                    theta_a = det_a.get('theta_object', 0.0)
                    theta_b = det_b.get('theta_object', 0.0)
                    s_a = det_a.get('s_object', 0.5)
                    s_b = det_b.get('s_object', 0.5)

                    # 校正到scene坐标系
                    if oa.singularity_type != SingularityType.O_SCENE:
                        dx_a, dy_a, dz_a = oa.offset_to_scene
                        s_a = self.offset_computer.correct_to_scene(
                            s_a, theta_a, oa.offset_to_scene,
                        )
                    if ob.singularity_type != SingularityType.O_SCENE:
                        dx_b, dy_b, dz_b = ob.offset_to_scene
                        s_b = self.offset_computer.correct_to_scene(
                            s_b, theta_b, ob.offset_to_scene,
                        )

                    rel = self.analyzer.analyze_relation(theta_a, s_a, theta_b, s_b)
                    rel.object_a = oa.object_id
                    rel.object_b = ob.object_id
                    cross_relations.append(rel)

        # Step 5: scene级余弦签名
        scene_theta_signature = {}
        for det in detections:
            obj = next((o for o in objects if o.label == det.get('label', '')), None)
            if obj:
                theta_obj = det.get('theta_object', 0.0)
                s_obj = det.get('s_object', 0.5)
                if obj.singularity_type != SingularityType.O_SCENE:
                    s_scene = self.offset_computer.correct_to_scene(
                        s_obj, theta_obj, obj.offset_to_scene,
                    )
                else:
                    s_scene = s_obj
                scene_theta_signature[obj.object_id] = round(s_scene, 4)

        return UnifiedSceneReport(
            scene_singularity=scene_singularity,
            objects=objects,
            cross_relations=cross_relations,
            scene_theta_signature=scene_theta_signature,
            unified=True,
            fallback_used=fallback_used,
            metadata={
                'n_objects': len(objects),
                'n_scene_ref': len([o for o in objects if o.singularity_type == SingularityType.O_SCENE]),
                'n_relations': len(cross_relations),
            }
        )


# ─────────────────────────────────────────────────────────────────────────────
# 自测
# ─────────────────────────────────────────────────────────────────────────────

def _selftest():
    print("=== SingularityUnifier 自测 ===\n")

    unifier = SingularityUnifier()

    # ── Test 1: 奇点分类 ──────────────────────────────────────
    print("--- Test 1: 奇点分类 ---")
    test_cases = [
        ('wall', (0, 0, 100, 400), False, SingularityType.O_SCENE),
        ('floor', (0, 400, 640, 480), False, SingularityType.O_SCENE),
        ('person', (200, 100, 280, 350), False, SingularityType.O_AGENT),
        ('person', (200, 100, 280, 350), True, SingularityType.O_AGENT),
        ('table', (100, 250, 500, 350), False, SingularityType.O_SCENE),
        ('book', (150, 280, 200, 310), False, SingularityType.O_OBJECT),
        ('chair', (50, 280, 120, 380), False, SingularityType.O_OBJECT),
        ('door', (0, 0, 80, 380), False, SingularityType.O_SCENE),
    ]
    for label, bbox, motion, expected in test_cases:
        result, conf = unifier.classify_object(label, bbox, motion)
        ok = 'PASS' if result == expected else 'FAIL'
        print(f"  [{ok}] {label:12s} motion={motion} -> {result.value} (conf={conf:.2f})")

    # ── Test 2: 简单场景统一 ─────────────────────────────────
    print("\n--- Test 2: 简单场景统一 ---")
    detections = [
        {'label': 'floor', 'bbox': (0, 350, 640, 480), 'motion': False,
         'theta_object': 0.0, 's_object': 0.3},
        {'label': 'wall', 'bbox': (0, 0, 10, 480), 'motion': False,
         'theta_object': 90.0, 's_object': 0.5},
        {'label': 'table', 'bbox': (200, 280, 500, 350), 'motion': False,
         'theta_object': 0.0, 's_object': 0.4},
        {'label': 'book', 'bbox': (300, 290, 380, 330), 'motion': False,
         'theta_object': 45.0, 's_object': 0.6},
    ]
    report = unifier.unify(detections, img_size=(480, 640))

    print(f"  Scene原点: {report.scene_singularity.position}")
    print(f"  Fallback: {report.fallback_used}")
    print(f"  物体数: {len(report.objects)}")
    for obj in report.objects:
        print(f"    {obj.object_id}: {obj.label:8s} → {obj.singularity_type.value} "
              f"offset=({obj.offset_to_scene[0]:.2f},{obj.offset_to_scene[1]:.2f})")

    print(f"  跨物体关系: {len(report.cross_relations)}")
    for rel in report.cross_relations:
        print(f"    {rel.object_a}  <->  {rel.object_b}: {rel.relation_type} "
              f"angle={rel.relative_angle}° parallel={rel.parallel_score:.2f}")

    # ── Test 3: 跨物体scene级余弦校验 ────────────────────────
    print("\n--- Test 3: scene级余弦校验 ---")
    # 桌面斜面(0°) vs 书本斜面(45°)
    table_theta, table_s = 0.0, 0.4
    book_theta, book_s = 45.0, 0.6
    rel = unifier.verify_scene(table_theta, table_s, book_theta, book_s)
    print(f"  table(θ={table_theta}°) vs book(θ={book_theta}°)")
    print(f"  → {rel.relation_type}, 相对角度={rel.relative_angle}° "
          f"parallel={rel.parallel_score:.2f} coplanar={rel.coplanar_score:.2f}")

    # ── Test 4: 多物体场景（模拟真实）─────────────────────────
    print("\n--- Test 4: 多物体场景 ---")
    detections2 = [
        {'label': 'wall_corner', 'bbox': (0, 0, 15, 480), 'motion': False, 'theta_object': 90.0, 's_object': 0.5},
        {'label': 'floor', 'bbox': (0, 400, 640, 480), 'motion': False, 'theta_object': 0.0, 's_object': 0.3},
        {'label': 'desk', 'bbox': (100, 260, 540, 320), 'motion': False, 'theta_object': 0.0, 's_object': 0.45},
        {'label': 'laptop', 'bbox': (200, 240, 350, 280), 'motion': False, 'theta_object': 15.0, 's_object': 0.55},
        {'label': 'mug', 'bbox': (420, 270, 460, 310), 'motion': False, 'theta_object': 30.0, 's_object': 0.5},
        {'label': 'person', 'bbox': (300, 150, 360, 320), 'motion': True, 'theta_object': 85.0, 's_object': 0.6},
    ]
    report2 = unifier.unify(detections2, img_size=(480, 640))
    print(f"  Scene原点: {report2.scene_singularity.position}")
    print(f"  参考物体: {report2.scene_singularity.reference_objects}")
    for obj in report2.objects:
        print(f"    {obj.label:12s} → {obj.singularity_type.value} "
              f"Δ=({obj.offset_to_scene[0]:.2f},{obj.offset_to_scene[1]:.2f})")
    for rel in report2.cross_relations:
        print(f"  {rel.object_a}  <->  {rel.object_b}: {rel.relation_type} "
              f"∠={rel.relative_angle}°")

    print("\n=== 自测通过 ===")


if __name__ == '__main__':
    _selftest()
