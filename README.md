# Cursor Settings 页面汉化 + 用量监控工具

## 工具简介

本工具用于将 Cursor IDE 的 Settings 页面（设置页面）以及部分 Cursor 新版界面从英文翻译为中文，同时在设置页面的用户信息区域下方实时显示 API 用量数据（总用量、高级模型用量、重置日期、倒计时等）。无论 Cursor 版本如何更新，只需重新运行脚本即可恢复汉化与用量显示。

当前版本在原有设置页汉化基础上，扩展了智能体窗口、市场插件页、插件详情页、输出面板、Git/变更面板、欢迎页、模型选择器等常见漏翻区域。

## 文件清单

| 文件 | 说明 |
|------|------|
| `CursorHanHua_GongJu.py` | Python 汉化注入主程序（核心脚本） |
| `QiDong_Cursor_ZhongWen.bat` | 一键启动批处理文件（自动注入 + 启动 Cursor） |
| `cursor_setting_lookup.js` | 辅助查找 Cursor 设置文案来源的工具 |
| `README.md` | 本说明文档 |

> 说明：`cmdow.exe` 已从这次贡献里移除，不再作为必须文件保留。

## 本次基于当前版本的更新内容

- 扩展汉化范围：补充智能体窗口、市场、插件页、插件详情页、模型选择器、Git/变更面板、输出面板、欢迎页、菜单项等漏翻内容。
- 支持拼接文案：针对 Cursor 中被图标、链接或变量拆开的句子，增加片段级翻译和页面级修正逻辑。
- 市场插件增强：插件名保留英文并追加中文括号名，例如 `Datadog（监控观测）`、`typescript-lsp（TypeScript 语言服务）`。
- 插件说明翻译：已知插件说明走内置词典；为保证市场打开速度，在线实时翻译默认关闭，可按需在开发者工具中开启。
- 插件详情页增强：技能名称保留原 ID，并追加中文用途，例如 `ddconfig（配置 Datadog）`。
- 增加市场页切换按钮：市场页右上角显示 `插件描述：中文/英文`，可切换插件说明显示语言。
- 路径配置改进：默认从脚本位置自动推断 Cursor 安装目录，也支持 `CURSOR_INSTALL_DIR` 和 `CURSOR_USER_DATA_DIR` 环境变量。
- 性能优化：全局修正节流、页面关键词判断、市场页识别缓存；市场页在线翻译默认关闭，减少 Cursor 启动和打开市场时的额外开销。
- 安全整理：新增 `.gitignore`，避免上传 `cursor_hanhua.js`、备份文件、缓存文件等可能包含本地信息的生成产物。

## 文件更新说明

- `CursorHanHua_GongJu.py`：增加了市场页、插件详情页、技能页、MCP、欢迎页、菜单、模型页等汉化；补了拼接文本处理、市场页开关按钮、在线翻译兜底和路径自动推断。
- `QiDong_Cursor_ZhongWen.bat`：改成顶部集中配置路径，方便用户直接对照截图修改；去掉了容易触发安全软件拦截的静默窗口辅助调用。
- `cursor_setting_lookup.js`：补了默认安装目录自动推断，方便查找 Cursor 设置字符串来源。
- `README.md`：补充本次更新内容、路径修改方式、市场翻译开关、性能优化和安全注意事项。

## 使用方法

### 方法一：一键启动（推荐）

推荐将本工具目录放在 Cursor 安装目录下或旁边，例如：

```text
D:\Tools\cursor\
  Cursor.exe
  resources\
  Cursor_chinese\
    CursorHanHua_GongJu.py
    QiDong_Cursor_ZhongWen.bat
```

双击 `QiDong_Cursor_ZhongWen.bat`，它会自动检测汉化状态并注入，然后启动 Cursor。

### 方法二：手动注入

```bash
# 注入汉化 + 用量显示
python CursorHanHua_GongJu.py

# 恢复原始英文
python CursorHanHua_GongJu.py --huifu
```

注入后需要 **重启 Cursor** 才能看到效果。

## 修改安装路径

现在批处理文件顶部直接给出了四个需要确认的路径，和你截图里保持一致：

```bat
set "CURSOR_INSTALL_DIR=C:\Program Files\Cursor"
set "CURSOR_USER_DIR=%APPDATA%\Cursor"
set "HANHUA_SCRIPT=%~dp0CursorHanHua_GongJu.py"
set "CURSOR_EXE=%CURSOR_INSTALL_DIR%\Cursor.exe"
set "WORKBENCH_HTML=%CURSOR_INSTALL_DIR%\resources\app\out\vs\code\electron-sandbox\workbench\workbench.html"
```

变量说明：

- `CURSOR_INSTALL_DIR`：Cursor 安装根目录，里面应包含 `Cursor.exe` 和 `resources\app`。
- `CURSOR_USER_DIR`：Cursor 用户数据目录，默认是 `%APPDATA%\Cursor`。如果你启动 Cursor 时使用了 `--user-data-dir`，这里要改成对应目录。
- `HANHUA_SCRIPT`：汉化脚本本体路径，默认使用 bat 同目录下的 `CursorHanHua_GongJu.py`。
- `CURSOR_EXE`：Cursor 可执行文件路径，通常是 `C:\Program Files\Cursor\Cursor.exe`。
- `WORKBENCH_HTML`：要注入的 `workbench.html` 路径，通常是 `C:\Program Files\Cursor\resources\app\out\vs\code\electron-sandbox\workbench\workbench.html`。

也可以打开 `CursorHanHua_GongJu.py`，查看文件开头的 **用户配置区域**：

```python
# ★★★ 用户配置区域 ★★★
CURSOR_AN_ZHUANG_LU_JING = CaiCe_Cursor_AnZhuang_LuJing()
CURSOR_SHU_JU_LU_JING    = CaiCe_Cursor_ShuJu_LuJing()
```

如果需要固定写死路径，可将它们改成您的 Cursor 实际安装路径和用户数据目录（存放认证令牌的目录）：

```python
CURSOR_AN_ZHUANG_LU_JING = r"D:\Tools\cursor"
CURSOR_SHU_JU_LU_JING    = r"%APPDATA%\Cursor"
```

## 工作原理

### 整体流程

```
Python 脚本
  ├── 1. 从 state.vscdb 数据库读取认证令牌
  ├── 2. 调用 Cursor API 获取用量数据（总次数、高级模型次数、计费周期等）
  ├── 3. 备份 workbench.html → workbench.html.bak
  ├── 4. 备份 product.json  → product.json.bak
  ├── 5. 生成 cursor_hanhua.js（翻译 + 用量数据）写入 Cursor 目录
  ├── 6. 在 workbench.html 中注入 <script> 标签引用翻译脚本
  └── 7. 重新计算 workbench.html 的 SHA256 哈希值并更新 product.json 中的 checksums
```

### 技术细节

1. **注入位置**：翻译脚本通过 `<script src="./cursor_hanhua.js">` 标签注入到 `workbench.html` 中，位于 `workbench.js` 之前加载。

2. **翻译机制**：`cursor_hanhua.js` 使用 JavaScript 的 `MutationObserver` API 监听 DOM 变化。当 Cursor Settings 页面渲染出英文文本时，脚本会实时将其替换为对应的中文翻译。

3. **翻译字典**：使用 `Map` 数据结构存储英文→中文的映射关系，查找效率为 O(1)；同时支持正则模式匹配，用于翻译带动态数字的文本（如 "3 requests remaining"）。

4. **拼接文本处理**：部分 Cursor 文案会被 DOM 拆成多段，例如中间夹着图标、链接或动态变量。脚本增加了片段级翻译和页面级修正逻辑，避免只翻译半句。

5. **市场插件翻译**：市场页和插件详情页会保留英文插件名，并追加中文括号名。插件说明优先使用内置词典。市场页右上角可通过 `插件描述：中文/英文` 按钮切换说明语言。为避免打开市场变慢，未知说明的在线翻译默认关闭；如确实需要，可在 Cursor 开发者工具中执行 `localStorage.setItem('cursor_hanhua_market_online_translate', '1')` 后重启 Cursor。

6. **技能与 MCP**：插件详情页里技能名称会显示中文括号名，技能说明也会尽量翻译成中文；MCP 名称也会尽量追加中文说明。

7. **用量显示**：脚本在 Cursor 设置页面的用户邮箱下方自动插入用量信息卡片，包含：
   - 总用量进度条（已用 / 总限额，颜色随使用率变化）
   - 高级模型（gpt-4 类）用量进度条
   - 计费周期重置日期
   - 今天的日期
   - 距重置日期的倒计时（≤3 天时变黄色预警）
   - 点击卡片可立即刷新用量数据，每 60 秒自动刷新一次

8. **认证方式**：脚本自动从 `state.vscdb`（Cursor 本地 SQLite 数据库）读取 `cursorAuth/accessToken`，无需手动配置 API Key。令牌以 Base64 编码嵌入 JS 文件，在浏览器端解码后用于 API 请求。

9. **性能保障**：
   - 所有翻译操作通过 `requestAnimationFrame` 批量合并到下一帧执行，不阻塞 UI 线程
   - 只处理新增/变化的 DOM 节点（增量翻译），不做全量扫描
   - 自动跳过编辑器区域（`.monaco-editor` 等），不影响代码编辑
   - 跳过 `<textarea>`、`<input>`、`<code>`、`<pre>` 等不应翻译的元素
   - 页面级修正带节流和关键词判断，避免普通页面反复扫描所有特殊修正规则
   - 市场页在线翻译默认关闭；如手动开启，也带本地缓存和单轮数量限制，减少打开页面时的卡顿

10. **版本兼容**：Cursor 更新时会覆盖 `workbench.html`，汉化注入会被清除。使用 `QiDong_Cursor_ZhongWen.bat` 启动时会自动检测并重新注入，因此无论版本如何更新都能保持汉化。

11. **幂等性**：脚本可重复运行，不会重复注入。如果检测到已注入，只会更新翻译 JS 文件内容（以便字典更新和用量数据刷新生效）。

12. **校验值同步**：Cursor 通过 `product.json` 中的 `checksums` 字段校验核心文件的 SHA256 哈希值。修改 `workbench.html` 后如不更新校验值，Cursor 启动时会提示 "Your Cursor installation appears to be corrupt. Please reinstall."。脚本会自动重新计算并更新校验值，避免此提示。

### 安全性

- 注入前自动创建 `workbench.html.bak` 和 `product.json.bak` 备份
- 可随时通过 `--huifu` 参数恢复全部原始文件（包括校验值）
- 翻译脚本仅修改文本节点的 `textContent`，不注入任何可执行代码
- 不修改 Cursor 的核心逻辑文件（`workbench.desktop.main.js` 等）
- 认证令牌以 Base64 编码存储于本地 JS 文件，不上传到任何第三方服务器

## 添加/修改翻译条目

翻译词典位于 `CursorHanHua_GongJu.py` 文件中 `ShengCheng_JS_DaiMa()` 函数内的 `FanYi_CiDian` Map。格式为 JavaScript Map 条目：

```javascript
["English Text", "中文翻译"],
```

正则模式匹配条目位于 `MoShi_FanYi` 数组中，格式为：

```javascript
[/正则表达式/i, "替换字符串（$1 表示捕获组）"],
```

**注意事项**：
- 中文翻译文本中 **不能包含中文全角引号**（`""`），否则会导致 JS 语法错误
- 如需在翻译中使用引号，请使用方括号 `[]` 或半角引号 `'` 替代
- 修改后重新运行 `python CursorHanHua_GongJu.py` 并重启 Cursor 即可生效

## 故障排除

| 问题 | 解决方案 |
|------|---------|
| 提示 "installation appears to be corrupt" | 重新运行 `python CursorHanHua_GongJu.py` 更新校验值 |
| 汉化完全无效 | 检查 JS 文件是否有语法错误：`node -c cursor_hanhua.js` |
| 部分文本未翻译 | 在 `FanYi_CiDian` 字典中添加对应的英文→中文映射 |
| 用量卡片不显示 | 检查 `CURSOR_SHU_JU_LU_JING` 路径是否正确，确认已登录 Cursor |
| 用量数据获取失败 | 检查网络连接，或令牌已过期（重新登录 Cursor 后重新运行脚本） |
| Cursor 启动异常 | 运行 `python CursorHanHua_GongJu.py --huifu` 恢复原始文件 |
| 更新后汉化消失 | 重新运行 `python CursorHanHua_GongJu.py` 或使用 bat 启动 |

**关于 "installation appears to be corrupt" 的原因**：Cursor（基于 VS Code/Electron）在 product.json 的 checksums 字段中记录了核心文件的 SHA256 哈希值。我们修改了 workbench.html 注入翻译脚本后，文件哈希变了，但 product.json 中记录的仍是原始哈希值，所以 Cursor 启动时检测到不一致就报此错误。

修复方式：`CursorHanHua_GongJu.py` 中的 `GengXin_JiaoYan_Zhi()` 函数在注入 HTML 后自动重新计算 workbench.html 的 SHA256 哈希值，并更新到 product.json 中。恢复时（`--huifu`）也会同步恢复 product.json 的原始值。
