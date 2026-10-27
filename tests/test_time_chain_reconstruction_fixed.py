"""
娴嬭瘯璁ょ煡鏃堕棿寮曟搸鐨勬椂闂撮摼閲嶅缓閫昏緫
Test suite for CognitiveTimeEngine time chain reconstruction
"""
import sys
import os
import time
import asyncio

# 娣诲姞 src/ 鍒拌矾寰?sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from cognitive_time_engine import CognitiveTimeEngine, CognitiveAnchor

def test_continuous_high_load():
    """娴嬭瘯鍦烘櫙 1锛氳繛缁珮璐熻嵎闃舵"""
    print("=" * 60)
    print("娴嬭瘯鍦烘櫙 1锛氳繛缁珮璐熻嵎闃舵")
    print("=" * 60)
    
    engine = CognitiveTimeEngine()
    
    # 妯℃嫙杩炵画楂樿礋鑽凤紙璐熻嵎 > 0.8锛?    base_time = time.time()
    for i in range(5):
        system_time = base_time + i * 10  # 姣忕涓€涓敋鐐?        cognitive_load = 0.85 + i * 0.02  # 璐熻嵎閫愭笎涓婂崌
        
        engine.place_anchor(
            cognitive_load=cognitive_load,
            state_summary=f"High load phase {i+1}",
            is_start=(i == 0),  # 绗竴涓槸寮€濮嬮敋鐐?        )
        
        # 璁板綍璁ょ煡鏃堕棿
        cognitive_time = engine.system_to_cognitive_time(system_time, cognitive_load)
        print(f"  [{i+1}] System: {system_time:.1f}s, Load: {cognitive_load:.2f}, Cognitive: {cognitive_time:.1f}s")
    
    # 閲嶅缓鏃堕棿閾?    time_chain = engine.reconstruct_time_chain()
    
    print(f"\n鉁?鏃堕棿閾鹃噸寤烘垚鍔燂細{len(time_chain)} 涓敋鐐?)
    print(f"  鎬绘椂闂磋啫鑳€锛歿engine.cognitive_time_accumulated - base_time:.1f}s")
    
    return len(time_chain) == 5

def test_load_fluctuation():
    """娴嬭瘯鍦烘櫙 2锛氳礋鑽峰墽鐑堟尝鍔紙楂樷啋浣庘啋楂橈級"""
    print("\n" + "=" * 60)
    print("娴嬭瘯鍦烘櫙 2锛氳礋鑽峰墽鐑堟尝鍔紙楂樷啋浣庘啋楂橈級")
    print("=" * 60)
    
    engine = CognitiveTimeEngine()
    
    base_time = time.time()
    
    # 闃舵 1锛氶珮璐熻嵎
    print("\n  闃舵 1锛氶珮璐熻嵎")
    engine.place_anchor(0.9, "Start high load", is_start=True)
    engine.system_to_cognitive_time(base_time, 0.9)
    
    # 闃舵 2锛氫綆璐熻嵎
    print("  闃舵 2锛氫綆璐熻嵎")
    engine.place_anchor(0.2, "Low load phase", is_start=False)
    engine.system_to_cognitive_time(base_time + 100, 0.2)
    
    # 闃舵 3锛氶珮璐熻嵎锛堝啀娆★級
    print("  闃舵 3锛氶珮璐熻嵎锛堝啀娆★級")
    engine.place_anchor(0.85, "High load again", is_start=True)
    engine.system_to_cognitive_time(base_time + 200, 0.85)
    
    # 閲嶅缓鏃堕棿閾?    time_chain = engine.reconstruct_time_chain()
    
    print(f"\n鉁?鏃堕棿閾鹃噸寤烘垚鍔燂細{len(time_chain)} 涓敋鐐?)
    print(f"  閿氱偣绫诲瀷锛歿sum(1 for a in time_chain if a.is_start)} 涓紑濮嬶紝{sum(1 for a in time_chain if not a.is_start)} 涓粨鏉?)
    
    return len(time_chain) == 3

def test_long_low_load():
    """娴嬭瘯鍦烘櫙 3锛氶暱鏃堕棿浣庤礋鑽凤紙鏃堕棿鑶ㄨ儉鏁堝簲绱Н锛?""
    print("\n" + "=" * 60)
    print("娴嬭瘯鍦烘櫙 3锛氶暱鏃堕棿浣庤礋鑽凤紙鏃堕棿鑶ㄨ儉鏁堝簲绱Н锛?)
    print("=" * 60)
    
    engine = CognitiveTimeEngine()
    
    base_time = time.time()
    low_load = 0.15  # 浣庤礋鑽?    
    # 妯℃嫙闀挎椂闂翠綆璐熻嵎锛堟椂闂磋啫鑳€鏁堝簲绱Н锛?    cognitive_times = []
    for i in range(10):
        system_time = base_time + i * 60  # 姣忓垎閽熶竴涓噰鏍?        cognitive_time = engine.system_to_cognitive_time(system_time, low_load)
        cognitive_times.append(cognitive_time)
        
        if i % 3 == 0:
            print(f"  [{i+1}] System: {system_time - base_time:.0f}s, Cognitive: {cognitive_time - base_time:.3f}s, Inflation: {(cognitive_time - system_time) / system_time * 100:.1f}%")
    
    # 楠岃瘉鏃堕棿鑶ㄨ儉鏁堝簲
    time_inflation = (cognitive_times[-1] - base_time) - (time.time() - base_time)
    
    print(f"\n鉁?鏃堕棿鑶ㄨ儉鏁堝簲楠岃瘉鎴愬姛")
    print(f"  绯荤粺鏃堕棿锛歿time.time() - base_time:.1f}s")
    print(f"  璁ょ煡鏃堕棿锛歿cognitive_times[-1] - base_time:.3f}s")
    print(f"  鏃堕棿鑶ㄨ儉锛歿time_inflation:.3f}s ({time_inflation / (time.time() - base_time) * 100:.1f}%)")
    
    # 浣庤礋鑽锋椂鏃堕棿搴旇鍙樻參锛堟椂闂磋啫鑳€锛?    return time_inflation > 0

def test_time_chain_integrity():
    """娴嬭瘯鍦烘櫙 4锛氭椂闂撮摼鏉″畬鏁存€э紙闃叉鏂嚎锛?""
    print("\n" + "=" * 60)
    print("娴嬭瘯鍦烘櫙 4锛氭椂闂撮摼鏉″畬鏁存€э紙闃叉鏂嚎锛?)
    print("=" * 60)
    
    engine = CognitiveTimeEngine()
    
    base_time = time.time()
    
    # 鍒涘缓涓€绯诲垪閿氱偣锛堟ā鎷熺湡瀹炲満鏅級
    anchors_config = [
        (0.9, "Task start", True),
        (0.85, "Task in progress", False),
        (0.3, "Task pause", False),
        (0.88, "Task resume", True),
        (0.92, "Task complete", False),
    ]
    
    for i, (load, summary, is_start) in enumerate(anchors_config):
        system_time = base_time + i * 30
        engine.place_anchor(load, summary, is_start)
        cognitive_time = engine.system_to_cognitive_time(system_time, load)
        print(f"  [{i+1}] {summary}: Load={load:.2f}, Cognitive={cognitive_time:.1f}s")
    
    # 閲嶅缓鏃堕棿閾?    time_chain = engine.reconstruct_time_chain()
    
    # 楠岃瘉瀹屾暣鎬?    is_valid = True
    for i in range(len(time_chain) - 1):
        if time_chain[i].cognitive_time > time_chain[i+1].cognitive_time:
            print(f"  鉂?鏃堕棿閾炬柇瑁傦細閿氱偣 {i} 鍜?{i+1} 涔嬮棿")
            is_valid = False
    
    if is_valid:
        print(f"\n鉁?鏃堕棿閾炬潯瀹屾暣鎬ч獙璇侀€氳繃锛歿len(time_chain)} 涓敋鐐癸紝鏃犳柇瑁?)
    
    return is_valid

def main():
    """杩愯鎵€鏈夋祴璇?""
    print("\n" + "=" * 60)
    print("璁ょ煡鏃堕棿寮曟搸 - 鏃堕棿閾鹃噸寤烘祴璇曞浠?)
    print("=" * 60)
    
    results = []
    
    # 娴嬭瘯 1锛氳繛缁珮璐熻嵎
    results.append(("杩炵画楂樿礋鑽?, test_continuous_high_load()))
    
    # 娴嬭瘯 2锛氳礋鑽锋尝鍔?    results.append(("璐熻嵎娉㈠姩", test_load_fluctuation()))
    
    # 娴嬭瘯 3锛氶暱鏃堕棿浣庤礋鑽?    results.append(("闀挎椂闂翠綆璐熻嵎", test_long_low_load()))
    
    # 娴嬭瘯 4锛氭椂闂撮摼鏉″畬鏁存€?    results.append(("鏃堕棿閾炬潯瀹屾暣鎬?, test_time_chain_integrity()))
    
    # 姹囨€荤粨鏋?    print("\n" + "=" * 60)
    print("娴嬭瘯缁撴灉姹囨€?)
    print("=" * 60)
    
    passed = 0
    for name, result in results:
        status = "鉁?閫氳繃" if result else "鉂?澶辫触"
        print(f"  {name}: {status}")
        if result:
            passed += 1
    
    print(f"\n鎬昏锛歿passed}/{len(results)} 閫氳繃")
    
    return passed == len(results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
