from pathlib import Path
root = Path.cwd()
assert (root / 'AGENTS.md').is_file() and (root / 'firmware/portrait36/platformio.ini').is_file(), 'Run at repository root'
changes = [
 ('tools/portrait_display/phone/index.html', 'placeholder="扫码自动填入，或输入32位连接码"', 'placeholder="输入屏上两行拼接后的32位连接码"'),
 ('tools/portrait_display/phone/index.html', '长按 UPDATE 键 2 秒进入配网。热点与连接码限时有效；按键显示连接信息会替换屏上当前画面。', '长按 UPDATE 键 2 秒进入配网。屏上连接码分两行，请拼接输入且不带空格；本版本不生成配网二维码。热点限时有效，显示配网信息会替换当前画面。'),
 ('tools/portrait_display/phone/app.js', '请扫描工牌上的链接，或输入32位临时连接码', '请输入屏上两行拼接后的32位临时连接码，或使用串口输出的完整链接'),
 ('firmware/portrait36/include/phone_service.h', '// keeps RF/AP OFF; configures BOOT input only', '// keeps RF/AP OFF; configures UPDATE input only'),
 ('firmware/portrait36/src/phone_service.cpp', 'APExpiringSoonHoldBootAndReupload', 'APExpiringSoonHoldUpdateAndReupload'),
]
original = {}; staged = {}
for relative, old, new in changes:
    path = root / relative
    if path not in original:
        original[path] = path.read_text(encoding='utf-8'); staged[path] = original[path]
    text = staged[path]
    if text.count(old) == 1 and text.count(new) == 0:
        staged[path] = text.replace(old, new, 1)
    elif text.count(old) == 0 and text.count(new) == 1:
        pass
    else:
        raise SystemExit(f'Content mismatch; no files written: {relative} / {old}')
for path, text in staged.items():
    if text != original[path]:
        path.write_text(text, encoding='utf-8'); print('UPDATED', path.relative_to(root))
    else:
        print('ALREADY UPDATED', path.relative_to(root))
print('Source copy fixed. Rebuild generated page and rerun software checks.')
