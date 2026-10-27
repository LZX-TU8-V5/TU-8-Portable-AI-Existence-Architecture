# -*- coding: utf-8 -*-


"""


entropy_guard.py — 注意力茧房防御：香农熵强制注入机制





来源：TODO_MASTER.md P1注意力茧房防御


目标：防止系统长期锁定在少数高频链条，形成注意力茧房





设计：


  记录每个链条激活频率 → 计算频率分布香农熵


  熵低于阈值 → 强制注入最低频链条（作为L1规则，不经LLM）


  紧急熔断：链条能量长期为零（>设定天数）→ 直接强制探测





熵公式：


  H = -sum(p_i * log(p_i))，i=1..N_chains


  H_max = log(N_chains)（均匀分布）


  H_normalized = H / H_max ∈ [0, 1]





阈值：


  H_normalized > 0.7 → 正常（各链条均衡激活）


  0.4 < H_norm <= 0.7 → 警告（茧房倾向）


  H_norm <= 0.4 → 强制注入（茧房已形成）


"""





import sys, math, json, time as time_module


from pathlib import Path


from dataclasses import dataclass


from typing import Optional


sys.path.insert(0, r'C:\Users\qq366410837\.qclaw\workspace\src')








# ─────────────────────────────────────────────────────────────────────────────


# 数据结构


# ─────────────────────────────────────────────────────────────────────────────





@dataclass


class ChainStats:


    """单个链条的激活统计"""


    chain_id: str


    activation_count: int = 0


    total_energy: float = 0.0


    last_activation_ts: float = 0.0


    force_injection_count: int = 0





    @property


    def avg_energy(self) -> float:


        return self.total_energy / max(1, self.activation_count)








@dataclass


class EntropyGuardReport:


    """熵守卫报告"""


    entropy: float


    normalized_entropy: float


    status: str                       # NORMAL / WARNING / FORCED / EMERGENCY


    chains_sorted: list               # [(chain_id, freq), ...] 升序（低频在前）


    dormant_chains: list              # 茧房链条（最低频）


    injection_triggered: bool


    injected_chain: Optional[str]


    n_chains: int


    metadata: dict








# ─────────────────────────────────────────────────────────────────────────────


# 熵守卫核心


# ─────────────────────────────────────────────────────────────────────────────





class EntropyGuard:


    """


    香农熵茧房防御。





    使用流程：


      guard = EntropyGuard()


      guard.record_activation('chain_A')           # 每当链条激活时调用


      guard.record_energy('chain_B', 0.8)         # 可选：记录能量


      report = guard.check()                       # 返回茧房状态


      if report.injection_triggered:


          chain = report.injected_chain


          ... # 强制探测该链条


    """





    # 归一化熵阈值


    THRESHOLD_WARNING = 0.7


    THRESHOLD_FORCED = 0.4


    # 紧急熔断：链条零激活超过此天数 → 强制探测


    EMERGENCY_DAYS = 3





    def __init__(self, state_file: Optional[str] = None):


        if state_file is None:


            state_file = str(Path(r'C:\Users\qq366410837\.qclaw\workspace\_agent_memory'


                                  r'\entropy_guard_state.json'))


        self.state_file = Path(state_file)


        self._state = self._load()





    # ── 状态管理 ────────────────────────────────────────────────────────────





    def _load(self) -> dict:


        if self.state_file.exists():


            try:


                return json.loads(self.state_file.read_text(encoding='utf-8'))


            except Exception:


                pass


        return self._default_state()





    def _default_state(self) -> dict:


        return {


            'chains': {},


            'total_activations': 0,


            'last_check_ts': 0.0,


            'injection_count': 0,


            'init_ts': time_module.time(),
            'reset_ts': 0.0,
        }





    def _to_chain(self, d: dict) -> ChainStats:


        return ChainStats(**{k: v for k, v in d.items() if k in ChainStats.__dataclass_fields__})





    def save(self) -> None:


        self.state_file.parent.mkdir(parents=True, exist_ok=True)


        state = self._state.copy()


        state['chains'] = {k: (v.__dict__ if isinstance(v, ChainStats) else v)


                           for k, v in self._state['chains'].items()}


        self.state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2),


                                  encoding='utf-8')





    # ── 记录接口 ────────────────────────────────────────────────────────────





    def record_activation(self, chain_id: str, energy: Optional[float] = None) -> None:


        """记录链条激活"""


        if chain_id not in self._state['chains']:


            self._state['chains'][chain_id] = {


                'chain_id': chain_id,


                'activation_count': 0,


                'total_energy': 0.0,


                'last_activation_ts': 0.0,


                'force_injection_count': 0,


            }


        c = self._state['chains'][chain_id]


        c['activation_count'] += 1


        c['last_activation_ts'] = time_module.time()


        if energy is not None:


            c['total_energy'] = c.get('total_energy', 0.0) + energy


        if c['activation_count'] == 0:
            c['was_activated'] = True
        self._state['total_activations'] += 1





    def record_energy(self, chain_id: str, energy: float) -> None:


        """仅记录能量（不计入激活次数）"""


        if chain_id not in self._state['chains']:


            self._state['chains'][chain_id] = {


                'chain_id': chain_id,


                'activation_count': 0,


                'total_energy': 0.0,


                'last_activation_ts': 0.0,


                'force_injection_count': 0,


            }


        c = self._state['chains'][chain_id]


        c['total_energy'] = c.get('total_energy', 0.0) + energy





    # ── 熵计算 ─────────────────────────────────────────────────────────────





    def _compute_entropy(self) -> tuple[float, float, list]:


        """Returns (entropy, normalized_entropy, sorted_chains)"""


        chains = {k: self._to_chain(v) for k, v in self._state['chains'].items()}


        n = len(chains)


        if n == 0:


            return 0.0, 0.0, []





        total = self._state['total_activations']


        if total == 0:


            return 0.0, 0.0, []





        freqs = [(cid, c.activation_count / total) for cid, c in chains.items()]


        freqs_sorted = sorted(freqs, key=lambda x: x[1])  # 升序（低频在前）





        H = 0.0


        for _, p in freqs:


            if p > 0:


                H -= p * math.log(p)





        H_max = math.log(n) if n > 1 else 1.0


        H_norm = H / H_max if H_max > 0 else 0.0


        return H, H_norm, freqs_sorted





    # ── 紧急熔断 ───────────────────────────────────────────────────────────





    def _emergency_chains(self) -> list:


        """返回长期零激活的链条（紧急熔断候选）"""


        now = time_module.time()


        threshold_s = self.EMERGENCY_DAYS * 86400


        return [


            cid for cid, c_dict in self._state['chains'].items()


            if c_dict['activation_count'] == 0


                and c_dict.get('was_activated', False)


                and (now - (c_dict['last_activation_ts']


                             if c_dict['last_activation_ts'] > 0


                             else self._state.get('reset_ts', 0))) > threshold_s


        ]





    # ── 茧房检测 ───────────────────────────────────────────────────────────





    def check(self) -> EntropyGuardReport:


        """执行茧房检测"""


        entropy, H_norm, freqs_sorted = self._compute_entropy()


        n_chains = len(self._state['chains'])


        now = time_module.time()





        n_dormant = max(1, int(n_chains * 0.2)) if n_chains > 0 else 1


        # dormant = low-freq but was ACTIVE (activation_count>0), excluding never-used chains
        dormant_chains = [cid for cid, _ in freqs_sorted
                          if self._state['chains'][cid]['activation_count'] > 0][:n_dormant]





        # 状态判定


        if H_norm > self.THRESHOLD_WARNING:


            status = 'NORMAL'


        elif H_norm > self.THRESHOLD_FORCED:


            status = 'WARNING'


        else:


            status = 'FORCED'





        # 注入判定


        injection_triggered = (status == 'FORCED')


        injected_chain = None





        if injection_triggered and dormant_chains:


            injected_chain = dormant_chains[0]


            self._state['injection_count'] += 1


            if injected_chain in self._state['chains']:


                self._state['chains'][injected_chain]['force_injection_count'] += 1





        # 紧急熔断（覆盖其他）


        emergency_chains = self._emergency_chains()


        if emergency_chains:


            injection_triggered = True


            injected_chain = emergency_chains[0]


            status = 'EMERGENCY'





        self._state['last_check_ts'] = now


        self.save()





        return EntropyGuardReport(


            entropy=round(entropy, 4),


            normalized_entropy=round(H_norm, 3),


            status=status,


            chains_sorted=freqs_sorted,


            dormant_chains=dormant_chains,


            injection_triggered=injection_triggered,


            injected_chain=injected_chain,


            n_chains=n_chains,


            metadata={


                'total_activations': self._state['total_activations'],


                'injection_count': self._state['injection_count'],


                'emergency_chains': emergency_chains,


                'threshold_warning': self.THRESHOLD_WARNING,


                'threshold_forced': self.THRESHOLD_FORCED,


            }


        )





    # ── 工具接口 ───────────────────────────────────────────────────────────





    def force_inject(self, chain_id: str) -> bool:


        """手动强制注入指定链条"""


        if chain_id in self._state['chains']:


            self._state['chains'][chain_id]['force_injection_count'] += 1


            self.save()


            return True


        return False





    def reset(self) -> None:


        """重置所有统计（保留链条列表）"""


        zombies = [cid for cid, c in self._state['chains'].items()


                   if c['activation_count'] == 0]


        for cid in zombies:


            del self._state['chains'][cid]


        for cid in self._state['chains']:


            if self._state['chains'][cid].get('activation_count', 0) > 0:


                self._state['chains'][cid]['was_activated'] = True


            self._state['chains'][cid]['activation_count'] = 0


            self._state['chains'][cid]['total_energy'] = 0.0


            self._state['chains'][cid]['last_activation_ts'] = 0.0


            self._state['chains'][cid]['force_injection_count'] = 0


        self._state['total_activations'] = 0


        self._state['injection_count'] = 0


        self._state['reset_ts'] = time_module.time()


        self.save()





    def get_status(self) -> dict:


        """快速状态查询"""


        entropy, H_norm, freqs = self._compute_entropy()


        n = len(self._state['chains'])


        n_dormant = max(1, int(n * 0.2))


        return {


            'n_chains': n,


            'total_activations': self._state['total_activations'],


            'H_norm': round(H_norm, 3),


            'status': 'NORMAL' if H_norm > self.THRESHOLD_WARNING else (


                      'WARNING' if H_norm > self.THRESHOLD_FORCED else 'FORCED'),


            'dormant_chains': [cid for cid, _ in freqs[:n_dormant]],


            'injection_count': self._state['injection_count'],


        }








# ─────────────────────────────────────────────────────────────────────────────


# 茧房感知路由器（用于集成到认知链路）


# ─────────────────────────────────────────────────────────────────────────────





class EntropyAwareRouter:


    """


    感知茧房状态的路由增强器。





    正常时：直接路由到置信度最高的链条


    WARNING时：低频链条权重+0.1（轻微boost）


    FORCED时：茧房链条优先（绕过置信度比较）


    """





    def __init__(self, guard: Optional[EntropyGuard] = None):


        self.guard = guard or EntropyGuard()





    def route_with_defense(


        self,


        candidates: list[tuple[str, float]],


    ) -> str:


        """


        带茧房防御的路由选择。





        Args:


            candidates: [(chain_id, confidence), ...]





        Returns:


            选中的chain_id


        """


        report = self.guard.check()





        if not report.injection_triggered or not report.injected_chain:


            return max(candidates, key=lambda x: x[1])[0] if candidates else ''





        # FORCED/EMERGENCY: 茧房链条优先


        dormant = report.injected_chain


        dormant_in_candidates = [c for c in candidates if c[0] == dormant]





        if dormant_in_candidates:


            return dormant





        # 茧房链条不在候选中 → boost最低频候选


        def boosted_conf(c):


            cid, conf = c


            for i, (lcid, _) in enumerate(report.chains_sorted):


                if lcid == cid:


                    boost = max(0, (len(report.chains_sorted) - i - 1) * 0.05)


                    return conf + boost


            return conf





        return max(candidates, key=boosted_conf)[0] if candidates else ''








# ─────────────────────────────────────────────────────────────────────────────


# 自测


# ─────────────────────────────────────────────────────────────────────────────





def _selftest():


    import tempfile, os





    print("=== EntropyGuard self-test ===\n")





    with tempfile.NamedTemporaryFile(suffix='.json', delete=False, mode='w') as f:


        tmp = f.name





    try:


        guard = EntropyGuard(state_file=tmp)





        # Test 1: 均匀分布 → 高熵


        print("--- Test 1: 均匀分布高熵 ---")


        for i in range(4):


            guard.record_activation(f'chain_{i}')


        report = guard.check()


        print(f"  4chains x1 each: H_norm={report.normalized_entropy:.3f} status={report.status}")


        assert report.normalized_entropy > 0.9, f"Expected ~1.0, got {report.normalized_entropy}"


        assert report.status == 'NORMAL'


        assert not report.injection_triggered


        print("  [PASS] 均匀分布熵接近1.0")





        # Test 2: 茧房：一条90% + 其余10%


        print("\n--- Test 2: 茧房检测 ---")


        guard.reset()


        for _ in range(90):


            guard.record_activation('dominant')


        for i in range(10):


            guard.record_activation(f'other_{i}')


        report = guard.check()


        print(f"  1x90 + 10x1: H_norm={report.normalized_entropy:.3f} status={report.status}")


        print(f"  dormant={report.dormant_chains} injected={report.injected_chain}")


        assert report.status in ('WARNING', 'FORCED')


        assert report.injection_triggered


        assert report.injected_chain is not None and report.injected_chain.startswith('other_'), f"Expected dormant other_X, got {report.injected_chain}"


        print("  [PASS] 茧房正确检测+注入最低频链条")





        # Test 3: 紧急熔断


        print("\n--- Test 3: 紧急熔断 ---")


        guard.reset()


        guard.record_activation('active_chain')


        guard._state['chains']['zombie_chain'] = {


            'chain_id': 'zombie_chain',


            'activation_count': 0,


            'total_energy': 0.0,


            'last_activation_ts': 0.0,


            'force_injection_count': 0,


            'was_activated': True,


            'last_activation_ts': time_module.time() - (EntropyGuard.EMERGENCY_DAYS + 1) * 86400,


        }


        report = guard.check()


        print(f"  zombie: status={report.status} emergency={report.metadata.get('emergency_chains', [])}")


        assert 'zombie_chain' in report.metadata.get('emergency_chains', [])


        assert report.injected_chain == 'zombie_chain'


        print("  [PASS] 紧急熔断正确")





        # Test 4: 茧房感知路由


        print("\n--- Test 4: 茧房感知路由 ---")


        guard.reset()


        for _ in range(80):


            guard.record_activation('chain_A')


        for _ in range(20):


            guard.record_activation('chain_B')


        guard.record_activation('chain_C')   # 只有1次


        router = EntropyAwareRouter(guard)


        candidates = [('chain_A', 0.9), ('chain_B', 0.7), ('chain_C', 0.6)]


        chosen = router.route_with_defense(candidates)


        print(f"  candidates={candidates}")


        print(f"  dormant_chain=chain_C (lowest freq)")


        print(f"  chosen={chosen}")


        assert chosen == 'chain_C', f"Expected chain_C, got {chosen}"


        print("  [PASS] 茧房路由优先注入最低频")





        # Test 5: 正常路由不干预


        print("\n--- Test 5: 正常路由不干预 ---")


        guard.reset()


        for i in range(4):


            for _ in range(25):


                guard.record_activation(f'chain_{i}')


        report = guard.check()


        print(f"  均衡4x25: H_norm={report.normalized_entropy:.3f} status={report.status}")


        assert report.status == 'NORMAL'


        assert not report.injection_triggered


        chosen = router.route_with_defense([('chain_0', 0.9), ('chain_1', 0.8)])


        assert chosen == 'chain_0', f"Expected chain_0, got {chosen}"


        print("  [PASS] 正常路由选最高置信度")





        # Test 6: 能量记录


        print("\n--- Test 6: 能量记录 ---")


        guard.reset()


        guard.record_activation('chain_X', energy=0.8)


        guard.record_activation('chain_X', energy=0.6)


        guard.record_activation('chain_X', energy=0.7)


        c = guard._to_chain(guard._state['chains']['chain_X'])


        print(f"  chain_X: count={c.activation_count} total={c.total_energy:.1f} avg={c.avg_energy:.2f}")


        assert c.activation_count == 3


        assert abs(c.total_energy - 2.1) < 0.01


        assert abs(c.avg_energy - 0.7) < 0.01


        print("  [PASS] 能量累计正确")





        # Test 7: 阈值边界


        print("\n--- Test 7: 阈值边界 ---")


        guard.reset()


        # 3链条：各1/3 → H_norm应接近1.0


        for i in range(3):


            guard.record_activation(f'ch_{i}')


        report = guard.check()


        print(f"  3chains x1: H_norm={report.normalized_entropy:.3f} status={report.status}")


        assert report.status == 'NORMAL'


        print("  [PASS] 3链条均匀NORMAL")





        print("\n=== ALL PASS ===")





    finally:


        try:


            os.unlink(tmp)


        except Exception:


            pass








if __name__ == '__main__':


    _selftest()


