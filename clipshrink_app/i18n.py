# -*- coding: utf-8 -*-
"""다국어 (i18n)."""

from __future__ import annotations

import ctypes

kernel32 = ctypes.windll.kernel32

SUPPORTED_LANGS = ("en", "ko", "ja", "zh", "es")

# GetUserDefaultUILanguage()의 primary language id → 언어 코드
_PRIMARY_LANG_MAP = {0x09: "en", 0x12: "ko", 0x11: "ja", 0x04: "zh", 0x0A: "es"}

STRINGS = {
    "en": {
        "tooltip": "ClipShrink v{ver} — auto-compress images for Discord's upload limit",
        "pause": "Pause watching",
        "resume": "Resume watching",
        "history": "Recent activity",
        "history_empty": "(none yet)",
        "upload_limit": "Upload limit",
        "open_folder": "Open output folder",
        "run_at_startup": "Run at Windows startup",
        "language": "Language",
        "lang_auto": "Auto-detect",
        "quit": "Quit",
        "notify_compress_done": "Compressed: {orig:.1f} MB → {new:.1f} MB (-{pct}%, {fmt}) — just paste it.",
        "notify_compress_fail": "Compression failed: couldn't get under the limit.",
        "notify_clipboard_fail": "Clipboard update failed: another app is using the clipboard. Please copy again in a moment.",
        "notify_file_deleted": "That file has already been deleted.",
        "notify_startup_fail": "Failed to change the startup setting.",
        "notify_first_run": "Running in the tray. To launch at startup, enable it from the menu → 'Run at Windows startup'.",
    },
    "ko": {
        "tooltip": "ClipShrink v{ver} — 디스코드 업로드 한도 자동 압축",
        "pause": "감시 중지",
        "resume": "감시 시작",
        "history": "최근 처리 내역",
        "history_empty": "(아직 없음)",
        "upload_limit": "업로드 한도",
        "open_folder": "처리된 이미지 폴더 열기",
        "run_at_startup": "Windows 시작 시 자동 실행",
        "language": "언어",
        "lang_auto": "자동 감지",
        "quit": "종료",
        "notify_compress_done": "압축 완료: {orig:.1f}MB → {new:.1f}MB ({pct}% 감소, {fmt}) — 그대로 붙여넣으세요.",
        "notify_compress_fail": "압축 실패: 한도 이하로 줄이지 못했습니다.",
        "notify_clipboard_fail": "클립보드 교체 실패: 다른 프로그램이 클립보드를 사용 중입니다. 잠시 후 다시 복사해 주세요.",
        "notify_file_deleted": "파일이 이미 삭제되었습니다.",
        "notify_startup_fail": "시작 프로그램 설정 변경에 실패했습니다.",
        "notify_first_run": "트레이에서 실행 중입니다. 부팅 시 자동 실행하려면 메뉴 → 'Windows 시작 시 자동 실행'을 켜세요.",
    },
    "ja": {
        "tooltip": "ClipShrink v{ver} — Discordのアップロード上限に自動圧縮",
        "pause": "監視を停止",
        "resume": "監視を再開",
        "history": "最近の処理履歴",
        "history_empty": "(まだありません)",
        "upload_limit": "アップロード上限",
        "open_folder": "出力フォルダーを開く",
        "run_at_startup": "Windows起動時に実行",
        "language": "言語",
        "lang_auto": "自動検出",
        "quit": "終了",
        "notify_compress_done": "圧縮完了: {orig:.1f}MB → {new:.1f}MB（{pct}%削減、{fmt}）— そのまま貼り付けてください。",
        "notify_compress_fail": "圧縮失敗: 上限以下に縮小できませんでした。",
        "notify_clipboard_fail": "クリップボードの更新に失敗: 他のアプリが使用中です。少し待ってからもう一度コピーしてください。",
        "notify_file_deleted": "ファイルはすでに削除されています。",
        "notify_startup_fail": "スタートアップ設定の変更に失敗しました。",
        "notify_first_run": "トレイで実行中です。起動時に自動実行するには、メニュー →「Windows起動時に実行」をオンにしてください。",
    },
    "zh": {
        "tooltip": "ClipShrink v{ver} — 自动压缩图片以符合 Discord 上传限制",
        "pause": "暂停监视",
        "resume": "恢复监视",
        "history": "最近处理记录",
        "history_empty": "(暂无)",
        "upload_limit": "上传限制",
        "open_folder": "打开输出文件夹",
        "run_at_startup": "开机时自动运行",
        "language": "语言",
        "lang_auto": "自动检测",
        "quit": "退出",
        "notify_compress_done": "压缩完成: {orig:.1f}MB → {new:.1f}MB（减少 {pct}%，{fmt}）— 直接粘贴即可。",
        "notify_compress_fail": "压缩失败: 无法缩小到限制以下。",
        "notify_clipboard_fail": "剪贴板更新失败: 其他程序正在占用剪贴板。请稍后重新复制。",
        "notify_file_deleted": "该文件已被删除。",
        "notify_startup_fail": "更改开机启动设置失败。",
        "notify_first_run": "正在托盘运行。如需开机自动启动，请在菜单 →「开机时自动运行」中开启。",
    },
    "es": {
        "tooltip": "ClipShrink v{ver} — comprime imágenes para el límite de subida de Discord",
        "pause": "Pausar la supervisión",
        "resume": "Reanudar la supervisión",
        "history": "Actividad reciente",
        "history_empty": "(nada todavía)",
        "upload_limit": "Límite de subida",
        "open_folder": "Abrir carpeta de salida",
        "run_at_startup": "Ejecutar al iniciar Windows",
        "language": "Idioma",
        "lang_auto": "Detección automática",
        "quit": "Salir",
        "notify_compress_done": "Comprimido: {orig:.1f} MB → {new:.1f} MB (-{pct}%, {fmt}) — solo pégalo.",
        "notify_compress_fail": "Error de compresión: no se pudo reducir por debajo del límite.",
        "notify_clipboard_fail": "Error al actualizar el portapapeles: otra aplicación lo está usando. Copia de nuevo en un momento.",
        "notify_file_deleted": "Ese archivo ya se ha eliminado.",
        "notify_startup_fail": "No se pudo cambiar la configuración de inicio.",
        "notify_first_run": "Ejecutándose en la bandeja. Para iniciar con el sistema, actívalo en el menú → 'Ejecutar al iniciar Windows'.",
    },
}

# ---------- 피커 (v2.0) 문자열 ----------
_PICKER_STRINGS = {
    "en": {
        "picker_open": "Open emoji & sticker picker",
        "hotkey_menu": "Picker hotkey",
        "hotkey_off": "Disabled",
        "notify_hotkey_fail": "Couldn't register hotkey {combo} — another app may be using it. Pick another in the tray menu.",
        "notify_webview2_missing": "The picker needs Microsoft Edge WebView2 Runtime (built into Windows 11). Compression still works.",
        "notify_paste_manual": "Ready in the clipboard — press Ctrl+V in Discord.",
        "picker_oversize_warn": "This item exceeds the upload limit and was sent as-is — Discord may reject it.",
        "picker_convert_warn": "Couldn't convert the animation — saved as a still image.",
        "picker_paste_no_image": "No image in the clipboard to add — copy an image first, or drop a file.",
        "picker_search": "Search",
        "picker_tab_emoji": "Emoji",
        "picker_tab_sticker": "Stickers",
        "picker_tab_gif": "GIFs",
        "picker_recent": "Recently used",
        "picker_empty": "Nothing here yet — press + to add, or drop image files.",
        "picker_hint": "Click = paste · Enter = first result · Esc = close · Right-click = more",
        "picker_add_title": "Add from Discord link",
        "picker_add_url_ph": "Paste an emoji/sticker link (cdn.discordapp.com/…)",
        "picker_add_name_ph": "Name (optional)",
        "picker_add_kw_ph": "Search keywords (optional)",
        "picker_add_note": "In Discord: right-click an emoji → Copy Link. Stickers without a link: save the image and drop the file here.",
        "picker_add_submit": "Add",
        "picker_cancel": "Close",
        "picker_folders_title": "Watched folders",
        "picker_add_folder": "Add folder to current tab",
        "picker_drop_hint": "Drop to add to this tab",
        "picker_ctx_file": "Paste as file",
        "picker_ctx_url": "Paste as link",
        "picker_ctx_delete": "Remove from library",
        "picker_err_lottie": "This is a Lottie sticker (.json) and can't be converted. Save it as an image and add the file instead.",
        "picker_err_not_discord": "That's not a Discord emoji/sticker link.",
        "picker_err_download": "Download failed — check the link or your connection.",
    },
    "ko": {
        "picker_open": "이모지·스티커 피커 열기",
        "hotkey_menu": "피커 단축키",
        "hotkey_off": "끄기",
        "notify_hotkey_fail": "단축키 {combo} 등록 실패 — 다른 앱이 사용 중일 수 있어요. 트레이 메뉴에서 다른 조합을 선택하세요.",
        "notify_webview2_missing": "피커에는 Microsoft Edge WebView2 런타임이 필요합니다(Windows 11 내장). 압축 기능은 계속 동작합니다.",
        "notify_paste_manual": "클립보드에 준비했습니다 — 디스코드에서 Ctrl+V 하세요.",
        "picker_oversize_warn": "업로드 한도를 넘는 항목이라 원본 그대로 보냈습니다 — 디스코드가 거부할 수 있어요.",
        "picker_convert_warn": "애니메이션을 변환하지 못해 정지 이미지로 저장했어요.",
        "picker_paste_no_image": "붙여넣을 이미지가 클립보드에 없어요 — 이미지를 먼저 복사하거나 파일을 끌어다 놓으세요.",
        "picker_search": "검색",
        "picker_tab_emoji": "이모지",
        "picker_tab_sticker": "스티커",
        "picker_tab_gif": "GIF",
        "picker_recent": "최근 사용",
        "picker_empty": "아직 비어 있어요 — ＋로 추가하거나 이미지 파일을 끌어다 놓으세요.",
        "picker_hint": "클릭=붙여넣기 · Enter=첫 항목 · Esc=닫기 · 우클릭=메뉴",
        "picker_add_title": "디스코드 링크로 추가",
        "picker_add_url_ph": "이모지/스티커 링크 붙여넣기 (cdn.discordapp.com/…)",
        "picker_add_name_ph": "이름 (선택)",
        "picker_add_kw_ph": "검색 키워드 (선택)",
        "picker_add_note": "디스코드에서 이모지 우클릭 → 링크 복사. 링크가 없는 스티커는 이미지를 저장해 여기로 끌어다 놓으세요.",
        "picker_add_submit": "추가",
        "picker_cancel": "닫기",
        "picker_folders_title": "감시 폴더",
        "picker_add_folder": "현재 탭에 폴더 추가",
        "picker_drop_hint": "놓으면 이 탭에 추가됩니다",
        "picker_ctx_file": "파일로 붙여넣기",
        "picker_ctx_url": "링크로 붙여넣기",
        "picker_ctx_delete": "라이브러리에서 삭제",
        "picker_err_lottie": "Lottie 스티커(.json)라서 변환할 수 없어요. 이미지로 저장한 뒤 파일로 추가해 주세요.",
        "picker_err_not_discord": "디스코드 이모지/스티커 링크가 아니에요.",
        "picker_err_download": "다운로드 실패 — 링크나 네트워크를 확인해 주세요.",
    },
    "ja": {
        "picker_open": "絵文字・スタンプピッカーを開く",
        "hotkey_menu": "ピッカーのホットキー",
        "hotkey_off": "無効",
        "notify_hotkey_fail": "ホットキー {combo} の登録に失敗しました — 他のアプリが使用中かもしれません。トレイメニューから別の組み合わせを選んでください。",
        "notify_webview2_missing": "ピッカーには Microsoft Edge WebView2 ランタイムが必要です（Windows 11 には内蔵）。圧縮機能は引き続き動作します。",
        "notify_paste_manual": "クリップボードに準備しました — Discord で Ctrl+V してください。",
        "picker_oversize_warn": "アップロード上限を超えるためそのまま送信しました — Discord に拒否される場合があります。",
        "picker_convert_warn": "アニメーションを変換できず、静止画像として保存しました。",
        "picker_paste_no_image": "貼り付ける画像がクリップボードにありません — 画像をコピーするか、ファイルをドロップしてください。",
        "picker_search": "検索",
        "picker_tab_emoji": "絵文字",
        "picker_tab_sticker": "スタンプ",
        "picker_tab_gif": "GIF",
        "picker_recent": "最近使用",
        "picker_empty": "まだ空です — ＋で追加するか、画像ファイルをドロップしてください。",
        "picker_hint": "クリック=貼り付け · Enter=先頭 · Esc=閉じる · 右クリック=メニュー",
        "picker_add_title": "Discord リンクから追加",
        "picker_add_url_ph": "絵文字/スタンプのリンクを貼り付け (cdn.discordapp.com/…)",
        "picker_add_name_ph": "名前（任意）",
        "picker_add_kw_ph": "検索キーワード（任意）",
        "picker_add_note": "Discord で絵文字を右クリック → リンクをコピー。リンクのないスタンプは画像を保存してここにドロップしてください。",
        "picker_add_submit": "追加",
        "picker_cancel": "閉じる",
        "picker_folders_title": "監視フォルダー",
        "picker_add_folder": "現在のタブにフォルダーを追加",
        "picker_drop_hint": "ドロップでこのタブに追加",
        "picker_ctx_file": "ファイルとして貼り付け",
        "picker_ctx_url": "リンクとして貼り付け",
        "picker_ctx_delete": "ライブラリから削除",
        "picker_err_lottie": "Lottie スタンプ（.json）のため変換できません。画像として保存してから追加してください。",
        "picker_err_not_discord": "Discord の絵文字/スタンプのリンクではありません。",
        "picker_err_download": "ダウンロードに失敗しました — リンクまたはネットワークを確認してください。",
    },
    "zh": {
        "picker_open": "打开表情·贴纸选择器",
        "hotkey_menu": "选择器快捷键",
        "hotkey_off": "禁用",
        "notify_hotkey_fail": "快捷键 {combo} 注册失败 — 可能被其他程序占用。请在托盘菜单中选择其他组合。",
        "notify_webview2_missing": "选择器需要 Microsoft Edge WebView2 运行时（Windows 11 已内置）。压缩功能仍可使用。",
        "notify_paste_manual": "已放入剪贴板 — 请在 Discord 中按 Ctrl+V。",
        "picker_oversize_warn": "该项目超过上传限制，已按原样发送 — Discord 可能会拒绝。",
        "picker_convert_warn": "无法转换动画，已保存为静态图片。",
        "picker_paste_no_image": "剪贴板中没有可添加的图片 — 请先复制图片，或拖入文件。",
        "picker_search": "搜索",
        "picker_tab_emoji": "表情",
        "picker_tab_sticker": "贴纸",
        "picker_tab_gif": "GIF",
        "picker_recent": "最近使用",
        "picker_empty": "这里还是空的 — 点 ＋ 添加，或拖入图片文件。",
        "picker_hint": "点击=粘贴 · Enter=第一项 · Esc=关闭 · 右键=菜单",
        "picker_add_title": "通过 Discord 链接添加",
        "picker_add_url_ph": "粘贴表情/贴纸链接 (cdn.discordapp.com/…)",
        "picker_add_name_ph": "名称（可选）",
        "picker_add_kw_ph": "搜索关键词（可选）",
        "picker_add_note": "在 Discord 中右键表情 → 复制链接。没有链接的贴纸请保存图片后拖到这里。",
        "picker_add_submit": "添加",
        "picker_cancel": "关闭",
        "picker_folders_title": "监视文件夹",
        "picker_add_folder": "为当前标签添加文件夹",
        "picker_drop_hint": "松开即添加到此标签",
        "picker_ctx_file": "作为文件粘贴",
        "picker_ctx_url": "作为链接粘贴",
        "picker_ctx_delete": "从库中删除",
        "picker_err_lottie": "这是 Lottie 贴纸（.json），无法转换。请先保存为图片再添加。",
        "picker_err_not_discord": "这不是 Discord 表情/贴纸链接。",
        "picker_err_download": "下载失败 — 请检查链接或网络。",
    },
    "es": {
        "picker_open": "Abrir selector de emojis y stickers",
        "hotkey_menu": "Atajo del selector",
        "hotkey_off": "Desactivado",
        "notify_hotkey_fail": "No se pudo registrar el atajo {combo}: otra aplicación puede estar usándolo. Elige otro en el menú de la bandeja.",
        "notify_webview2_missing": "El selector necesita Microsoft Edge WebView2 Runtime (incluido en Windows 11). La compresión sigue funcionando.",
        "notify_paste_manual": "Listo en el portapapeles — pulsa Ctrl+V en Discord.",
        "picker_oversize_warn": "Este elemento supera el límite de subida y se envió tal cual — Discord podría rechazarlo.",
        "picker_convert_warn": "No se pudo convertir la animación — se guardó como imagen fija.",
        "picker_paste_no_image": "No hay ninguna imagen en el portapapeles para añadir — copia una imagen o suelta un archivo.",
        "picker_search": "Buscar",
        "picker_tab_emoji": "Emojis",
        "picker_tab_sticker": "Stickers",
        "picker_tab_gif": "GIF",
        "picker_recent": "Usados recientemente",
        "picker_empty": "Aún no hay nada — pulsa ＋ para añadir o suelta archivos de imagen.",
        "picker_hint": "Clic=pegar · Enter=primero · Esc=cerrar · Clic derecho=menú",
        "picker_add_title": "Añadir desde enlace de Discord",
        "picker_add_url_ph": "Pega un enlace de emoji/sticker (cdn.discordapp.com/…)",
        "picker_add_name_ph": "Nombre (opcional)",
        "picker_add_kw_ph": "Palabras clave (opcional)",
        "picker_add_note": "En Discord: clic derecho en un emoji → Copiar enlace. Para stickers sin enlace, guarda la imagen y suéltala aquí.",
        "picker_add_submit": "Añadir",
        "picker_cancel": "Cerrar",
        "picker_folders_title": "Carpetas vigiladas",
        "picker_add_folder": "Añadir carpeta a esta pestaña",
        "picker_drop_hint": "Suelta para añadir a esta pestaña",
        "picker_ctx_file": "Pegar como archivo",
        "picker_ctx_url": "Pegar como enlace",
        "picker_ctx_delete": "Eliminar de la biblioteca",
        "picker_err_lottie": "Es un sticker Lottie (.json) y no se puede convertir. Guárdalo como imagen y añádelo como archivo.",
        "picker_err_not_discord": "No es un enlace de emoji/sticker de Discord.",
        "picker_err_download": "Error de descarga — comprueba el enlace o tu conexión.",
    },
}

for _lang, _table in _PICKER_STRINGS.items():
    STRINGS[_lang].update(_table)
del _PICKER_STRINGS

current_lang = "en"  # 실행 시 set_language()로 설정됨


def detect_system_lang() -> str:
    """Windows UI 언어를 감지해 지원 언어 코드로 매핑 (실패 시 'en')."""
    try:
        langid = kernel32.GetUserDefaultUILanguage()
        return _PRIMARY_LANG_MAP.get(langid & 0x3FF, "en")
    except Exception:
        return "en"


def set_language(pref: str):
    """pref가 'auto'면 시스템 언어를 감지, 아니면 해당 언어로 설정."""
    global current_lang
    if pref == "auto":
        current_lang = detect_system_lang()
    elif pref in STRINGS:
        current_lang = pref
    else:
        current_lang = "en"


def tr(key: str, **kwargs) -> str:
    """현재 언어의 문자열을 반환 (없으면 영어, 그래도 없으면 key)."""
    table = STRINGS.get(current_lang, STRINGS["en"])
    text = table.get(key) or STRINGS["en"].get(key, key)
    return text.format(**kwargs) if kwargs else text
