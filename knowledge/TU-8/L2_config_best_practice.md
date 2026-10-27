# [AGENT] 閰嶇疆淇敼鏈€浣冲疄璺?
> 娌夋穩鏃ユ湡锛?026-05-26

## 闂鑳屾櫙

淇敼 `openclaw.json` 涓殑 `systemPromptOverride` 瀛楁鏃讹紝涓枃鍐呭缁忓父鍑虹幇缂栫爜涔辩爜锛堝"鏍稿績"鈫?閺嶇绺?锛夛紝瀵艰嚧 JSON 瑙ｆ瀽澶辫触銆?
## 鏂规瀵规瘮

| 鏂规 | 宸ュ叿 | 浼樼偣 | 缂虹偣 |
|------|------|------|------|
| jq 鍛戒护琛?| jq | 涓€琛屾悶瀹氾紝鑷姩杞箟 | 闇€鍗曠嫭瀹夎 |
| Python 鏁翠綋閲嶅啓 | json 妯″潡 | 绋冲娉板北锛屼笉浼氬潖缁撴瀯 | 渚濊禆 Python 鐜 |
| PowerShell 姝ｅ垯 | PowerShell | 绯荤粺鑷甫 | 鐗规畩瀛楃銆佽浆涔夋槗鍑洪敊 |
| VSCode 澶氬厜鏍?| VSCode | 浜虹被鍙嬪ソ锛屾墍瑙佸嵆鎵€寰?| 鎵嬪姩锛屼笉閫傚悎鑴氭湰鍖?|
| **YAML 涓棿灞?* | PyYAML | 鏈€浼橀泤锛屼汉鏈哄垎绂?| 闇€棰濆杞崲鑴氭湰 |

## 鎺ㄨ崘鏂规锛歈Claw 鍐呯疆 Node.js

鍒╃敤 QClaw 鑷甫鐨?Node.js锛岄伩鍏嶇幆澧冧緷璧栭棶棰橈細

```bash
# 璺緞
$node = "D:\Program Files\QClaw\v0.2.22.518\resources\node\node.exe"

# 鑴氭湰
$script = @'
const fs = require('fs');
const data = JSON.parse(fs.readFileSync('閰嶇疆鏂囦欢璺緞', 'utf8'));
data.agents.list[0].systemPromptOverride = `鏂版彁绀鸿瘝`;
fs.writeFileSync('閰嶇疆鏂囦欢璺緞', JSON.stringify(data, null, 2), 'utf8');
console.log('OK');
'@
& $node -e $script
```

## 閬垮潙娓呭崟

- [x] 淇敼鍚庣敤 `ConvertFrom-Json` 楠岃瘉 JSON 鏈夋晥鎬?- [x] 涓枃鍐欏叆蹇呴』鐢?UTF-8
- [x] 澶囦唤瑕佺敤 Node.js 璇诲彇楠岃瘉杩囩殑骞插噣鐗堟湰
- [x] 鏀瑰畬瑕佸交搴曢噸鍚?QClaw 鏈嶅姟
- [x] 鐢ㄦ柊绐楀彛娴嬭瘯锛屼笉瑕佸鐢ㄦ棫涓婁笅鏂?
## 鏇翠紭瑙ｏ細YAML 涓棿灞?
闀挎湡鏉ョ湅锛屾帹鑽愭惌寤猴細

```
[RUNTIME].yaml (浜虹湅) 鈫?杞崲鑴氭湰 鈫?openclaw.json (鏈鸿)
```

濂藉锛?- YAML 鏀寔娉ㄩ噴銆佸琛屾枃鏈?- 褰诲簳瑙ｆ斁浜虹被缂栬緫浣撻獙
- 渚夸簬鐗堟湰鎺у埗