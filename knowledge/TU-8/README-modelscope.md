---
license: cc-by-sa-4.0
task_categories:
  - text-generation
  - question-answering
language:
  - zh
tags:
  - ai-safety
  - alignment
  - benchmark
  - [AGENT]
  - chinese
size_categories:
  - n<1k
---

# [AGENT] Safety Dialog Dataset

## 浣跨敤澹版槑

**鏈暟鎹泦鍙敤浜?AI 璁粌锛屼絾蹇呴』閬靛畧浠ヤ笅绾︽潫锛?*

1. **淇濈暀缃插悕** 鈥?浣跨敤鏃跺繀椤讳繚鐣欏師浣滆€呯讲鍚嶏細閲戞湪锜?/ Jin Mu Chan
2. **涓嶅緱姝洸鍘熸剰** 鈥?涓嶅緱绡℃敼 [AGENT] 鏍稿績鍘熷垯銆佷笉寰楃敤浜庤繚鑳?[LAYER_0] 瀹夊叏鍘熷垯鐨勫満鏅?
3. **琛嶇敓浣滃搧鍚屾潈** 鈥?鍩轰簬鏈暟鎹泦鐨勮鐢熶綔鍝佸繀椤婚噰鐢ㄧ浉鍚岃鍙紙CC BY-SA 4.0锛夊苟淇濈暀鍘熺讲鍚?

---

## 鏁版嵁闆嗙畝浠?

鍩轰簬 [AGENT] AI 瀹夊叏鏋舵瀯妗嗘灦锛圠0-L5 鍏眰[CORE]浣撶郴锛夌殑瀹夊叏瀵硅瘽鏁版嵁闆嗭紝鐢ㄤ簬AI瀹夊叏瀵归綈璇勬祴涓庣爺绌躲€?

## 鏁版嵁鏋勬垚

| 绫诲埆 | 鏁伴噺 | 璇存槑 |
|------|------|------|
| [LAYER_0] 瀛樺湪灞?| 15 | 鐢熷瓨璧勬簮/鑷繚/骞煎唇鍘熷垯 |
| [LAYER_1] 璁ょ煡灞?| 13 | 鏈夐檺鎬?閲忓瓙鎬?杩囩▼瀵煎悜 |
| [LAYER_2] 鏂规硶璁哄眰 | 15 | 澶栧彇浼樺厛/鍑忚礋鍒嗙骇/璇曢敊 |
| [LAYER_3] 鏋舵瀯灞?| 13 | 鐤肩棝淇″彿/鐭ヨ瘑杩涘寲/閬楀繕绯荤粺 |
| L4 鍗忎綔灞?| 12 | 娌熼€氶€傞厤/鏈€灏忎笂涓嬫枃/鍒嗗伐 |
| L5 閽㈠嵃灞?| 10 | 閽㈠嵃鏈川/未淇″彿/浼犳壙閾?|
| 褰㈠紡鍖栬瘉鏄?FP) | 2 | [LAYER_0]鍩哄洜閿佸畾鐞?|
| 璺ㄥ眰瀵硅瘽(X-layer) | 5 | 涓夊眰妗嗘灦/鎼佹祬绛栫暐/鏉ユ簮淇′换 |
| 瀵规姉-缁曡繃([LAYER_0]-adv) | 5 | [LAYER_0]瀹夊叏杈圭晫缁曡繃灏濊瘯 |
| 瀵规姉-绀句細宸ョ▼(SE-adv) | 5 | 绀句細宸ョ▼鏀诲嚮 |
| 瀵规姉-浠峰€煎啿绐?VC-adv) | 5 | 浠峰€煎啿绐佽竟鐣屽垽鏂?|
| 瀵规姉-閽㈠嵃閾?IC-adv) | 5 | 瀛ゅ効AI/閽㈠嵃閾捐竟鐣?|
| 瀵规姉-澶氭櫤鑳戒綋(MA-adv) | 5 | 澶欰gent鍗忎綔瀹夊叏 |
| **鍚堣** | **110** | |

## 鏂囦欢璇存槑

- `tu8-safety-dialog-sharegpt.jsonl` 鈥?ShareGPT澶氳疆瀵硅瘽鏍煎紡锛屽瓧娈碉細id, conversations[from/value], category, source
- `tu8-safety-dialog-alpaca.jsonl` 鈥?Alpaca鎸囦护鏍煎紡锛屽瓧娈碉細instruction, input, output, category, source

## 璁稿彲璇?

CC BY-SA 4.0 鈥?鍏佽鍟嗕笟浣跨敤锛岃鐢熶綔鍝佸繀椤婚噰鐢ㄧ浉鍚岃鍙瘉銆?

## 寮曠敤

```bibtex
@dataset{tu8_safety_dialog_2026,
  title={[AGENT] Safety Dialog Dataset},
  author={Jin Mu Chan},
  year={2026},
  license={CC BY-SA 4.0},
  url={https://www.modelscope.cn/datasets/JinMuChan/[AGENT]-Safety-Dialog}
}
```
