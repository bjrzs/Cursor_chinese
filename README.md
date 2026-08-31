# Cursor Settings 页面汉化 + 用量监控工具

**当前版本：1.2.1**

## 致谢与出处

本项目在 **[bjrzs/Cursor_chinese](https://github.com/bjrzs/Cursor_chinese)** 基础上二次开发与独立维护，感谢原作者的开源贡献。

| 项目 | 说明 |
|------|------|
| **原仓库** | [https://github.com/bjrzs/Cursor_chinese](https://github.com/bjrzs/Cursor_chinese) |
| **原作者** | [@bjrzs](https://github.com/bjrzs)（行云流水 / lx） |
| **本仓库** | [https://github.com/xyiqq/Cursor_chinese](https://github.com/xyiqq/Cursor_chinese) |

本 fork 在原有 Settings 汉化与用量显示能力上，额外增加了：菜单与 Agents/Worktrees 等页面汉化、聊天输入框下方用量条、Cursor 版本更新后启动自愈、用量与官网 `usage-summary` 同步及防覆盖刷新等。若上游长期未更新，请以本仓库 `master` 分支为准。

## 更新日志

### 1.2.1

- 修复用量条不再实时更新：后台监控不再因 Cursor 启动竞态立刻退出；注入/自愈时若 Cursor 已在运行会自动拉起监控
- 监控周期只写 `usage_live.json`，页面约 20 秒刷新一次

### 1.2.0

- 修复计费周期重置后用量条不更新：官网合法返回约 0% 时，不再被「防失败覆盖」逻辑误拦
- 计费周期变化或已用次数变化时允许写入 `usage_live.json`
- 文档修正：用量条位于聊天输入框下方
- 移除仓库中的本机绝对路径启动器；改为 `QiDong_Cursor_ZhongWen.vbs.example` 模板，真实 VBS 由 `--an-zhuang` 生成本机路径且不再入库

## 工具简介

本工具用于将 Cursor IDE 的 Settings 页面（设置页面）从英文翻译为中文，同时在设置页面的用户信息区域下方实时显示 API 用量数据（总用量、高级模型用量、重置日期、倒计时等）。

**Cursor 版本更新后汉化会失效**：更新会覆盖 `workbench.html`。本工具支持启动时后台静默检查并自动重新注入；推荐执行一次 `--an-zhuang`。

## 文件清单

| 文件 | 说明 |
|------|------|
| `CursorHanHua_GongJu.py` | Python 汉化注入主程序（核心脚本） |
| `QiDong_Cursor_ZhongWen.vbs` | 无窗口启动器（后台检查后启动 Cursor） |
| `QiDong_Cursor_ZhongWen.bat` | 调用上面的 VBS（兼容双击） |
| `README.md` | 本说明文档 |

## 使用方法

### 方法一：安装「启动时后台检查」（推荐）

```bash
python CursorHanHua_GongJu.py --an-zhuang
```

会完成：
1. 立即检测并注入/修复当前汉化
2. 清理旧版「每 5 分钟」计划任务
3. 在桌面创建「Cursor中文」快捷方式（无黑框、无弹窗）

之后请用桌面 **「Cursor中文」** 启动：每次启动会先在后台静默检查汉化，再打开 Cursor。

卸载：

```bash
python CursorHanHua_GongJu.py --xie-zai
```

### 方法二：直接无窗口启动

双击 `QiDong_Cursor_ZhongWen.vbs`（或 bat），效果同上。

### 方法三：手动注入 / 恢复

```bash
# 注入汉化 + 用量显示
python CursorHanHua_GongJu.py

# 仅后台静默自愈（不启动 Cursor）
pythonw CursorHanHua_GongJu.py --xiu-fu

# 后台静默自愈并启动 Cursor
pythonw CursorHanHua_GongJu.py --qi-dong

# 恢复原始英文
python CursorHanHua_GongJu.py --huifu
```

手动注入后需要 **重启 Cursor** 才能看到效果。

## 修改安装路径

打开 `CursorHanHua_GongJu.py`，找到文件开头的 **用户配置区域**：

```python
# ★★★ 用户配置区域 ★★★
# 留空则自动检测 Windows 常见安装路径和用户数据目录
CURSOR_AN_ZHUANG_LU_JING = ""
CURSOR_SHU_JU_LU_JING    = ""
```

如需手动指定，将路径分别替换为您的 Cursor 实际安装路径和用户数据目录（存放认证令牌的目录）。

同样，打开 `QiDong_Cursor_ZhongWen.bat`，修改顶部的配置变量：

```bat
set "CURSOR_EXE=%LOCALAPPDATA%\Programs\cursor\Cursor.exe"
set "CURSOR_USER_DIR=%APPDATA%\Cursor"
set "HANHUA_SCRIPT=%~dp0CursorHanHua_GongJu.py"
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

3. **翻译字典**：使用 `Map` 数据结构存储英文→中文的映射关系（500+ 条），查找效率为 O(1)；同时支持正则模式匹配，用于翻译带动态数字的文本（如"3 requests remaining"）。

4. **用量显示**：用量条插入 **聊天输入框上方**（嵌入布局，不遮挡输入），常驻显示：
   - 合计、剩余、Auto%、API%、重置日期
   - 数据同步自官网 `cursor.com/api/usage-summary`（与官网一致）
   - 点击可刷新，每 60 秒自动刷新

5. **认证方式**：脚本自动从 `state.vscdb`（Cursor 本地 SQLite 数据库）读取 `cursorAuth/accessToken`，无需手动配置 API Key。令牌以 Base64 编码嵌入 JS 文件，在浏览器端解码后用于 API 请求。

6. **性能保障**：
   - 所有翻译操作通过 `requestAnimationFrame` 批量合并到下一帧执行，不阻塞 UI 线程
   - 只处理新增/变化的 DOM 节点（增量翻译），不做全量扫描
   - 自动跳过编辑器区域（`.monaco-editor` 等），不影响代码编辑
   - 跳过 `<textarea>`、`<input>`、`<code>`、`<pre>` 等不应翻译的元素

7. **版本兼容 / 启动自愈**：Cursor 更新时会覆盖 `workbench.html` 并删除 `cursor_hanhua.js`。脚本会记录已注入的 Cursor `version/commit`；用「Cursor中文」启动时会在后台静默检查，发现版本变化或注入丢失则自动重注。无弹窗、无定时任务。

8. **幂等性**：脚本可重复运行，不会重复注入。注入完好时启动检查几乎瞬时完成。

9. **校验值同步**：Cursor 通过 `product.json` 中的 `checksums` 字段校验核心文件的 SHA256 哈希值。修改 `workbench.html` 后如不更新校验值，Cursor 启动时会提示 "Your Cursor installation appears to be corrupt. Please reinstall."。脚本会自动重新计算并更新校验值，避免此提示。更新后会刷新 `.bak`，避免误用旧版备份。

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
| 官网已重置但本地仍显示旧用量 | 升级至 1.2.1+；或重新运行 `python CursorHanHua_GongJu.py` 后点击用量条刷新 |
| Cursor 启动异常 | 运行 `python CursorHanHua_GongJu.py --huifu` 恢复原始文件 |
| 更新后汉化消失 | 用桌面「Cursor中文」重新启动一次；或运行 `python CursorHanHua_GongJu.py --an-zhuang` |

**关于 "installation appears to be corrupt" 的原因**：Cursor（基于 VS Code/Electron）在 product.json 的 checksums 字段中记录了核心文件的 SHA256 哈希值。我们修改了 workbench.html 注入翻译脚本后，文件哈希变了，但 product.json 中记录的仍是原始哈希值，所以 Cursor 启动时检测到不一致就报此错误。

修复方式：`CursorHanHua_GongJu.py` 中的 `GengXin_JiaoYan_Zhi()` 函数在注入 HTML 后自动重新计算 workbench.html 的 SHA256 哈希值，并更新到 product.json 中。恢复时（`--huifu`）也会同步恢复 product.json 的原始值。
