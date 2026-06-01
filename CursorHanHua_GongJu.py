# -*- coding: utf-8 -*-
"""
Cursor 汉化 + 用量监控工具
功能：
  1. 将翻译脚本注入 Cursor 的 workbench.html，实现设置页面中文化
  2. 自动从本地数据库读取认证令牌，调用 API 获取用量数据
  3. 在 Cursor 设置页面用户信息区域下方显示实时用量情况

用法：
  python CursorHanHua_GongJu.py           汉化 + 用量显示
  python CursorHanHua_GongJu.py --huifu   恢复原始文件
"""

import os  # 文件路径操作
import sys  # 系统参数
import shutil  # 文件复制
import datetime  # 时间戳
import hashlib  # 哈希计算
import base64  # Base64 编码
import json  # JSON 读写
import sqlite3  # SQLite 数据库
import urllib.request  # HTTP 请求
import urllib.error  # HTTP 错误处理


def ZhanKai_LuJing(LuJing):
    """Expand environment variables and user home markers in a path."""
    if not LuJing:
        return ""
    return os.path.abspath(os.path.expandvars(os.path.expanduser(LuJing)))


def HuoQu_Cursor_App_MuLu(LuJing):
    """Return Cursor's resources/app directory for Windows or macOS installs."""
    LuJing = ZhanKai_LuJing(LuJing)
    HouXuan = [
        os.path.join(LuJing, "resources", "app"),
        os.path.join(LuJing, "Contents", "Resources", "app"),
        LuJing,
    ]
    for MuLu in HouXuan:
        if os.path.exists(os.path.join(MuLu, "product.json")) and os.path.exists(os.path.join(MuLu, "out")):
            return MuLu
    return os.path.join(LuJing, "resources", "app")


def Shi_Cursor_AnZhuang_LuJing(LuJing):
    """Check whether a candidate points to a Cursor install or resources/app directory."""
    if not LuJing:
        return False
    App_MuLu = HuoQu_Cursor_App_MuLu(LuJing)
    Workbench = os.path.join(App_MuLu, "out", "vs", "code", "electron-sandbox", "workbench", "workbench.html")
    return os.path.exists(os.path.join(App_MuLu, "product.json")) and os.path.exists(Workbench)


def CaiCe_Cursor_AnZhuang_LuJing():
    """优先使用环境变量，否则从脚本位置和常见安装目录推断 Cursor 根目录。"""
    HuanJing = os.environ.get("CURSOR_INSTALL_DIR") or os.environ.get("CURSOR_ROOT")
    HouXuan = []
    if HuanJing:
        HouXuan.append(ZhanKai_LuJing(HuanJing))

    JiaoBen_MuLu = os.path.dirname(os.path.abspath(__file__))
    HouXuan.extend([
        os.path.dirname(JiaoBen_MuLu),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "cursor"),
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Cursor"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Cursor"),
        "/Applications/Cursor.app",
        os.path.join(os.path.expanduser("~"), "Applications", "Cursor.app"),
    ])

    for LuJing in HouXuan:
        LuJing = ZhanKai_LuJing(LuJing)
        if Shi_Cursor_AnZhuang_LuJing(LuJing):
            return LuJing

    return ZhanKai_LuJing(HuanJing or os.path.dirname(JiaoBen_MuLu))


def CaiCe_Cursor_ShuJu_LuJing():
    """优先使用环境变量，否则使用当前用户默认 Cursor 数据目录。"""
    HuanJing = os.environ.get("CURSOR_USER_DATA_DIR")
    if HuanJing:
        return ZhanKai_LuJing(HuanJing)

    AppData = os.environ.get("APPDATA")
    if AppData:
        return os.path.join(AppData, "Cursor")

    if sys.platform == "darwin":
        return os.path.join(os.path.expanduser("~"), "Library", "Application Support", "Cursor")

    if os.name == "posix":
        return os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config")), "Cursor")

    return os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "Cursor")


# ============================================================
# ★★★ 用户配置区域 ★★★
# ============================================================

# Cursor 安装根目录。
# 可通过环境变量 CURSOR_INSTALL_DIR 覆盖，例如：
#   set CURSOR_INSTALL_DIR=D:\Tools\cursor
CURSOR_AN_ZHUANG_LU_JING = CaiCe_Cursor_AnZhuang_LuJing()

# Cursor 用户数据目录（存放认证令牌等）
# 如果使用 --user-data-dir 自定义了目录，可通过 CURSOR_USER_DATA_DIR 覆盖。
CURSOR_SHU_JU_LU_JING = CaiCe_Cursor_ShuJu_LuJing()

# 以下路径一般不需要修改
GONG_ZUO_TAI_HTML_XIANG_DUI = os.path.join("out", "vs", "code", "electron-sandbox", "workbench")  # workbench 目录相对路径
GONG_ZUO_TAI_HTML_MING = "workbench.html"  # workbench HTML 文件名
HAN_HUA_JS_MING = "cursor_hanhua.js"  # 翻译脚本文件名
ZHU_RU_BIAO_JI = "<!-- CURSOR_HANHUA_INJECTION -->"  # 注入标记
BEI_FEN_HOU_ZHUI = ".bak"  # 备份文件后缀

# API 端点
API_YONG_LIANG = "https://api2.cursor.sh/auth/usage"  # 高级请求用量
API_YONG_LIANG_ZONG_JIE = "https://www.cursor.com/api/usage-summary"  # 总用量摘要
API_GE_REN_XIN_XI = "https://api2.cursor.sh/auth/full_stripe_profile"  # 个人信息

# state.vscdb 中的认证键名
DB_XIANG_DUI_LU_JING = os.path.join("User", "globalStorage", "state.vscdb")  # 数据库相对路径
LING_PAI_JIAN_MING = "cursorAuth/accessToken"  # 访问令牌键名
YOU_XIANG_JIAN_MING = "cursorAuth/cachedEmail"  # 邮箱键名

# Cursor 内置扩展的简中桥接翻译。
# VS Code 官方语言包不会覆盖 anysphere.*，这里补上最常见的私有扩展元信息。
KUO_ZHAN_FAN_YI_QIAO_JIE = {
    "anysphere.cursor-always-local": {
        "package": {
            "displayName": "Cursor 始终本地",
            "description": "为 Cursor 提供实验性本地功能。"
        }
    },
    "anysphere.cursor-retrieval": {
        "package": {
            "displayName": "Cursor 检索",
            "description": "处理 Cursor 的索引与检索能力。"
        }
    },
    "anysphere.cursor-shadow-workspace": {
        "package": {
            "displayName": "Cursor 影子工作区",
            "description": "管理一个供 AI 智能体在展示前整理代码的隐藏本地窗口。"
        }
    }
}


# ============================================================
# ★★★ 认证与 API 函数 ★★★
# ============================================================

def DuQu_FangWen_LingPai():
    """从 Cursor 本地 state.vscdb 数据库读取访问令牌和用户邮箱"""
    ShuJuKu_LuJing = os.path.join(CURSOR_SHU_JU_LU_JING, DB_XIANG_DUI_LU_JING)  # 数据库完整路径
    if not os.path.exists(ShuJuKu_LuJing):  # 检查数据库是否存在
        print(f"[警告] 未找到 Cursor 数据库: {ShuJuKu_LuJing}")
        return None, None

    try:
        LianJie = sqlite3.connect(ShuJuKu_LuJing)  # 连接数据库
        YouBiao = LianJie.cursor()  # 创建游标

        YouBiao.execute("SELECT value FROM ItemTable WHERE key=?", (LING_PAI_JIAN_MING,))  # 查询访问令牌
        JieGuo = YouBiao.fetchone()  # 获取结果
        LingPai = JieGuo[0] if JieGuo else None  # 提取令牌值

        YouBiao.execute("SELECT value FROM ItemTable WHERE key=?", (YOU_XIANG_JIAN_MING,))  # 查询邮箱
        JieGuo = YouBiao.fetchone()  # 获取结果
        YouXiang = JieGuo[0] if JieGuo else None  # 提取邮箱值

        LianJie.close()  # 关闭数据库连接
        return LingPai, YouXiang  # 返回令牌和邮箱
    except Exception as CuoWu:
        print(f"[警告] 读取数据库失败: {CuoWu}")
        return None, None


def GouZao_Cookie(LingPai):
    """从访问令牌构造 WorkosCursorSessionToken Cookie"""
    try:
        BuFen = LingPai.split('.')  # JWT 由三部分组成
        if len(BuFen) >= 2:  # 至少需要 header 和 payload
            TianChong = BuFen[1] + '=' * (4 - len(BuFen[1]) % 4)  # 补齐 Base64 填充
            JieXi = json.loads(base64.b64decode(TianChong).decode('utf-8'))  # 解码 payload
            YongHu_Id = JieXi.get('sub', '').replace('auth0|', '')  # 提取用户 ID
            return f"{YongHu_Id}::{LingPai}"  # 组合为 Cookie 格式
    except Exception:
        pass
    return None


def HuoQu_YongLiang_ZongJie(LingPai):
    """调用 cursor.com/api/usage-summary 获取总用量摘要"""
    Cookie_Zhi = GouZao_Cookie(LingPai)  # 构造 Cookie
    if not Cookie_Zhi:  # Cookie 构造失败
        return None

    try:
        QingQiu = urllib.request.Request(API_YONG_LIANG_ZONG_JIE)  # 创建请求
        QingQiu.add_header('Cookie', f'WorkosCursorSessionToken={Cookie_Zhi}')  # 添加认证 Cookie
        QingQiu.add_header('Accept', 'application/json')  # 期望 JSON 响应
        XiangYing = urllib.request.urlopen(QingQiu, timeout=10)  # 发送请求
        return json.loads(XiangYing.read().decode('utf-8'))  # 解析 JSON 响应
    except Exception as CuoWu:
        print(f"[警告] 获取总用量摘要失败: {CuoWu}")
        return None


def HuoQu_GaoJi_YongLiang(LingPai):
    """调用 api2.cursor.sh/auth/usage 获取高级请求用量"""
    try:
        QingQiu = urllib.request.Request(API_YONG_LIANG)  # 创建请求
        QingQiu.add_header('Authorization', f'Bearer {LingPai}')  # Bearer 令牌认证
        QingQiu.add_header('Accept', 'application/json')  # 期望 JSON 响应
        XiangYing = urllib.request.urlopen(QingQiu, timeout=10)  # 发送请求
        return json.loads(XiangYing.read().decode('utf-8'))  # 解析 JSON 响应
    except Exception as CuoWu:
        print(f"[警告] 获取高级请求用量失败: {CuoWu}")
        return None


def ZhengHe_YongLiang_ShuJu(LingPai):
    """整合所有用量数据为统一格式"""
    ShuJu = {  # 默认数据结构
        "zongYong": 0,       # 总使用次数
        "zongXian": 2000,    # 总限额（PRO 默认 2000）
        "shengYu": 2000,     # 剩余次数
        "gaoJiYong": 0,      # 高级请求使用次数
        "gaoJiXian": 500,    # 高级请求限额（PRO 默认 500）
        "zongBaiFen": 0,     # 总使用百分比
        "apiBaiFen": 0,      # API 使用百分比
        "jiFeiKaiShi": "",   # 计费周期开始
        "jiFeiJieShu": "",   # 计费周期结束
        "gengXinShiJian": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # 数据更新时间
        "jiHua": "pro",      # 计划类型
        "youXiao": False,    # 数据是否有效
        "moXingXiangQing": {}  # 各模型详细用量
    }

    # 获取总用量摘要
    ZongJie = HuoQu_YongLiang_ZongJie(LingPai)  # 调用 API
    if ZongJie and 'individualUsage' in ZongJie:  # 有有效数据
        JiHua = ZongJie['individualUsage'].get('plan', {})  # 提取计划用量
        ShuJu["zongYong"] = JiHua.get('used', 0)  # 已使用次数
        ShuJu["zongXian"] = JiHua.get('limit', 2000)  # 总限额
        ShuJu["shengYu"] = JiHua.get('remaining', 0)  # 剩余次数
        ShuJu["zongBaiFen"] = round(JiHua.get('totalPercentUsed', 0), 1)  # 总百分比
        ShuJu["apiBaiFen"] = round(JiHua.get('apiPercentUsed', 0), 1)  # API 百分比
        ShuJu["jiHua"] = ZongJie.get('membershipType', 'pro')  # 计划类型
        ShuJu["youXiao"] = True  # 标记为有效

        # 解析计费周期日期
        KaiShi = ZongJie.get('billingCycleStart', '')  # 开始日期
        JieShu = ZongJie.get('billingCycleEnd', '')  # 结束日期
        if KaiShi:
            ShuJu["jiFeiKaiShi"] = KaiShi[:10]  # 只取日期部分
        if JieShu:
            ShuJu["jiFeiJieShu"] = JieShu[:10]  # 只取日期部分

    # 获取高级请求用量（含各模型详细数据）
    GaoJi = HuoQu_GaoJi_YongLiang(LingPai)  # 调用 API
    if GaoJi:
        MoXing_ShuJu = {}  # 模型详情字典
        for JianMing in GaoJi:
            if JianMing == 'startOfMonth':  # 跳过非模型键
                continue
            MoXing_XinXi = GaoJi[JianMing]  # 提取模型数据
            MoXing_ShuJu[JianMing] = {
                "qingQiu": MoXing_XinXi.get('numRequests', 0),       # 请求数
                "shangXian": MoXing_XinXi.get('maxRequestUsage', 0),  # 请求上限
                "lingPaiShu": MoXing_XinXi.get('numTokens', 0)       # Token 数
            }
        ShuJu["moXingXiangQing"] = MoXing_ShuJu  # 存入模型详情
        # 总用量 zongYong 保持来自 usage-summary 的 plan.used，不在此覆盖

        if 'gpt-4' in GaoJi:  # 有 gpt-4 类别数据
            ShuJu["gaoJiYong"] = GaoJi['gpt-4'].get('numRequests', 0)
            ShuJu["gaoJiXian"] = GaoJi['gpt-4'].get('maxRequestUsage', 500)

        # 从 startOfMonth 补充计费周期（兜底，当 usage-summary 未取到时）
        if not ShuJu["jiFeiJieShu"] and 'startOfMonth' in GaoJi:
            try:
                KaiShiRi = datetime.datetime.fromisoformat(GaoJi['startOfMonth'].replace('Z', '+00:00'))
                ShuJu["jiFeiKaiShi"] = KaiShiRi.strftime('%Y-%m-%d')
                Nian = KaiShiRi.year + (KaiShiRi.month // 12)
                Yue = (KaiShiRi.month % 12) + 1
                JieShuRi = KaiShiRi.replace(year=Nian, month=Yue)
                ShuJu["jiFeiJieShu"] = JieShuRi.strftime('%Y-%m-%d')
            except Exception:
                pass

        if not ShuJu["youXiao"]:
            ShuJu["youXiao"] = True

    return ShuJu  # 返回整合后的数据


# ============================================================
# ★★★ JavaScript 代码生成 ★★★
# ============================================================

def ShengCheng_JS_DaiMa(YongLiang_ShuJu, YuanShi_LingPai=""):
    """生成包含翻译、用量显示和实时刷新的完整 JavaScript 代码"""

    # 将用量数据序列化为 JSON
    YongLiang_Json = json.dumps(YongLiang_ShuJu, ensure_ascii=False)  # 用量 JSON 字符串

    # 将令牌 Base64 编码后嵌入（基础保护，防止明文出现）
    BianMa_LingPai_Str = ""
    if YuanShi_LingPai:
        BianMa_LingPai_Str = base64.b64encode(YuanShi_LingPai.encode('utf-8')).decode('utf-8')

    return '''\
/*
 * Cursor 汉化 + 用量监控脚本
 * Auto-generated by CursorHanHua_GongJu.py
 * Generated: ''' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '''
 */
(function() {
    'use strict';

    // ================================================================
    // SECTION 1: 翻译字典
    // ================================================================

    var FanYi_CiDian = new Map([
        // ==================== 左侧导航栏 ====================
        ["General", "通用"],
        ["Agents", "智能体"],
        ["Tab", "代码补全"],
        ["Cloud Agents", "云端智能体"],
        ["Plugins", "插件"],
        ["Rules, Skills, Subagents", "规则、技能、子智能体"],
        ["Tools & MCP", "工具与 MCP"],
        ["Hooks", "钩子"],
        ["Indexing & Docs", "索引与文档"],
        ["Network", "网络"],
        ["Marketplace", "市场"],
        ["Beta", "测试版"],
        ["Features", "功能"],
        ["Models", "模型"],
        ["Rules", "规则"],
        ["Docs", "文档"],
        ["Search settings Ctrl+F", "搜索设置 Ctrl+F"],
        ["Search settings", "搜索设置"],
        ["Pro Plan", "专业版计划"],

        // ==================== 通用 (General) 页面 ====================
        ["Account", "账户"],
        ["Sign In", "登录"],
        ["Sign Out", "退出登录"],
        ["Log In", "登录"],
        ["Log Out", "退出登录"],
        ["Logout", "退出登录"],
        ["Manage Subscription", "管理订阅"],
        ["Manage Account", "管理账户"],
        ["Manage", "管理"],
        ["Manage your account and billing", "管理您的账户和账单"],
        ["Plan & Usage", "计划与用量"],
        ["CURRENT PLAN", "当前计划"],
        ["UPGRADE AVAILABLE", "可升级"],
        ["Upgrade Available", "可升级"],
        ["Included in Pro", "Pro 已包含"],
        ["Included In Pro", "Pro 已包含"],
        ["Resets on", "重置日期"],
        ["Agent", "智能体"],
        ["Auto", "自动"],
        ["Composer", "Composer"],
        ["Auto + Composer", "自动 + Composer"],
        ["API", "API"],
        ["API used", "API 已用"],
        ["Auto used", "Auto 已用"],
        ["Additional usage beyond limits consumes API quota or on-demand spend.", "超出限额的额外用量会消耗 API 配额或按需消费。"],
        ["Additional usage beyond limits consumes on-demand spend. Your plan includes at least $20 of API usage.", "超出限额的额外用量会产生按需消费。您的计划至少包含 20 美元 API 用量。"],
        ["Upgrade", "升级"],
        ["Upgrade to Pro", "升级到专业版"],
        ["Upgrade to Pro now", "立即升级到专业版"],
        ["Upgrade Plan", "升级计划"],
        ["Free", "免费版"],
        ["Pro", "专业版"],
        ["Business", "企业版"],
        ["Usage", "用量"],
        ["On-Demand", "按需"],
        ["On-Demand Spending", "按需消费"],
        ["On-Demand Usage", "按需用量"],
        ["On-demand spending is currently disabled", "按需消费目前已禁用"],
        ["On-Demand usage is consumed after a usage limit is reached, and is billed in arrears.", "按需用量在达到使用限额后消耗，采用后付费方式计费。"],
        ["Enable on-demand usage to go beyond your plan's included usage. Requires a paid plan.", "启用按需用量以超出计划包含的用量。需要付费计划。"],
        ["Monthly Limit", "每月限额"],
        ["Set a fixed amount or make it unlimited.", "设置固定金额或设为无限制。"],
        ["Fixed", "固定"],
        ["Unlimited", "无限制"],
        ["Total", "合计"],
        ["Unlock 3x more usage on Agent & more", "解锁 Agent 3 倍用量及更多"],
        ["Free 7-day trial", "免费 7 天试用"],
        ["Start Plan Now", "立即开始计划"],
        ["Start Pro Now", "立即开始专业版"],
        ["Start Pro+ Now", "立即开始 Pro+"],
        ["Get Pro+", "获取 Pro+"],
        ["Get Ultra", "获取 Ultra"],
        ["Sign in to get started with Cursor's AI features", "登录以开始使用 Cursor 的 AI 功能"],

        // -- 隐私与遥测 --
        ["Privacy", "隐私"],
        ["Privacy Mode", "隐私模式"],
        ["Privacy mode", "隐私模式"],
        ["Privacy Mode Enabled", "隐私模式已启用"],
        ["Privacy Mode (Legacy)", "隐私模式（旧版）"],
        ["Enable Privacy Mode", "启用隐私模式"],
        ["Share Data", "共享数据"],
        ["Data Sharing Enabled", "数据共享已启用"],
        ["When enabled, none of your code will ever be stored by us.", "启用后，我们将不会存储您的任何代码。"],
        ["None of your code will be stored by us.", "我们不会存储您的任何代码。"],
        ["Your code may be used for training.", "您的代码可能会被用于训练。"],
        ["Your code data will not be trained on or used to improve the product. We will not store your code.", "您的代码数据不会被用于训练或用于改进产品。我们不会存储您的代码。"],
        ["Privacy Mode (Legacy) is enabled. Background Agent and some features not available.", "隐私模式（旧版）已启用。后台 Agent 和部分功能不可用。"],
        ["Enabled", "已启用"],
        ["Disabled", "已禁用"],
        ["enabled", "已启用"],
        ["disabled", "已禁用"],
        ["Failed to update privacy settings", "隐私设置更新失败"],
        ["Hide Email Address", "隐藏邮箱地址"],
        ["Hide Email", "隐藏邮箱"],
        ["Partially mask your email address in the Cursor user interface", "在 Cursor 用户界面中部分隐藏您的邮箱地址"],
        ["Share Now", "立即共享"],
        ["Switch to Privacy Mode", "切换到隐私模式"],
        ["Data Sharing is paused for your first day of usage.", "数据共享在您使用的第一天暂停。"],
        ["No training. Code may be stored for Background Agent and other features.", "不用于训练。代码可能会为后台 Agent 和其他功能而存储。"],
        ["No training and no storage. Background Agent and other features that require code storage will be disabled.", "不用于训练且不存储。后台 Agent 和其他需要代码存储的功能将被禁用。"],
        ["Cloud Agents are not available when your privacy mode is set to disable data storage. To use Cloud Agents, please update your privacy settings to allow data storage.", "当隐私模式设置为禁止数据存储时，云端智能体不可用。要使用云端智能体，请更新隐私设置以允许数据存储。"],
        ["Cloud Agents require data storage to function.", "云端智能体需要数据存储才能运行。"],
        ["Cloud Agents are disabled because your privacy mode prevents data storage. Update your privacy settings to enable Cloud Agents.", "由于您的隐私模式阻止了数据存储，云端智能体已被禁用。请更新隐私设置以启用云端智能体。"],

        // -- 编辑器/外观 --
        ["Appearance", "外观"],
        ["Editor", "编辑器"],
        ["Editor Settings", "编辑器设置"],
        ["Editor (Classic)", "编辑器（经典）"],
        ["Configure font, formatting, minimap and more", "配置字体、格式化、小地图等"],
        ["Theme", "主题"],
        ["Keyboard Shortcuts", "键盘快捷键"],
        ["Configure keyboard shortcuts", "配置键盘快捷键"],
        ["Color Theme", "颜色主题"],
        ["File Icon Theme", "文件图标主题"],
        ["Product Icon Theme", "产品图标主题"],
        ["Font Size", "字体大小"],
        ["Font Family", "字体"],
        ["Line Height", "行高"],
        ["Tab Size", "Tab 大小"],
        ["Word Wrap", "自动换行"],
        ["Auto Save", "自动保存"],
        ["Format On Save", "保存时格式化"],
        ["Minimap", "小地图"],
        ["Breadcrumbs", "面包屑导航"],
        ["Layout", "布局"],
        ["Default Layout", "默认布局"],
        ["Choose the default layout for new windows and workspaces", "选择新窗口和工作区的默认布局"],
        ["Zen", "禅模式"],
        ["Status Bar", "状态栏"],
        ["Show status bar", "显示状态栏"],
        ["Title Bar", "标题栏"],
        ["Show title bar in agent layout", "在智能体布局中显示标题栏"],
        ["Auto-hide editor when empty", "编辑器为空时自动隐藏"],
        ["When all editors are closed, hide the editor area and maximize chat", "当所有编辑器关闭时，隐藏编辑器区域并最大化聊天"],
        ["Sync layouts across windows", "跨窗口同步布局"],
        ["When enabled, all windows share the same layout", "启用后，所有窗口共享相同的布局"],
        ["Review Control Location", "审查控件位置"],
        ["Show inline diff review controls in top level breadcrumbs or floating island", "在顶级面包屑导航或浮动岛中显示内联差异审查控件"],
        ["Open chat as editor tabs", "以编辑器标签页打开对话"],
        ["Show chats as editor tabs inside the chat area instead of the legacy stacked view", "在聊天区域内以编辑器标签页显示对话，而不是旧的堆叠视图"],
        ["Open chat as editor tabs is unavailable while non-chat content is placed in the Secondary Side Bar.", "当非聊天内容放置在辅助侧栏中时，以编辑器标签页打开对话不可用。"],

        // -- 外观 - 颜色 --
        ["Colors", "颜色"],
        ["Hue", "色相"],
        ["Choose a tint color", "选择色调颜色"],
        ["Intensity", "强度"],
        ["Control how strongly the tint is applied", "控制色调的应用强度"],
        ["Reduce Transparency", "减少透明度"],
        ["Replace translucent surfaces with opaque backgrounds", "将半透明表面替换为不透明背景"],

        // -- 外观 - 排版 --
        ["Typography", "排版"],
        ["UI Font Size", "界面字体大小"],
        ["Font size for the Cursor user interface", "Cursor 用户界面的字体大小"],
        ["Code Font Size", "代码字体大小"],
        ["Font size for code editors and diffs", "代码编辑器和差异对比的字体大小"],
        ["UI Font Family", "界面字体"],
        ["Override the Cursor user interface typeface", "覆盖 Cursor 用户界面的字体"],
        ["Code Font Family", "代码字体"],
        ["Override the font for code editors and diffs", "覆盖代码编辑器和差异对比的字体"],
        ["System font", "系统字体"],
        ["System monospace", "系统等宽字体"],

        // -- 外观 - 主题选项 --
        ["Choose between light, dark, or high contrast themes", "在浅色、深色或高对比度主题之间选择"],
        ["High contrast", "高对比度"],
        ["Light", "浅色"],
        ["Dark", "深色"],

        // -- 导入与更新 --
        ["Cursor Account", "Cursor 账户"],
        ["Import Settings from VS Code", "从 VS Code 导入设置"],
        ["Import settings, extensions, and keybindings from VS Code", "从 VS Code 导入设置、扩展和快捷键"],
        ["Importing", "导入中"],
        ["VS Code import completed!", "VS Code 导入完成！"],
        ["Update Access", "更新通道"],
        ["Early Access", "抢先体验"],
        ["Nightly", "每日构建"],
        ["By default, get notifications for stable updates. In Early Access, pre-release builds may be unstable for production work.", "默认情况下，您将收到稳定版更新通知。在抢先体验中，预发布版本可能不适合生产使用。"],
        ["Dogfood", "内测版"],
        ["Warning: Updates Apply Automatically", "警告：更新将自动应用"],
        ["This track will silently download and install updates without prompting whenever Cursor is closed.", "此通道将在 Cursor 关闭时静默下载并安装更新，不会提示。"],
        ["Notifications", "通知"],
        ["System Notifications", "系统通知"],
        ["System Tray Icon", "系统任务栏图标"],
        ["Show system notifications when Agent completes or needs attention", "当 Agent 完成或需要关注时显示系统通知"],
        ["Warning Notifications", "警告通知"],
        ["Show warning-level in-app toasts", "显示警告级别的应用内提示"],
        ["Menu Bar Icon", "菜单栏图标"],
        ["Show Cursor in menu bar", "在菜单栏中显示 Cursor"],
        ["Show Cursor in system tray", "在系统托盘中显示 Cursor"],
        ["Show status bar at the bottom of the window", "在窗口底部显示状态栏"],

        // -- 工具栏 --
        ["Toolbar on Selection", "选中时显示工具栏"],
        ["Show Add to Chat & Quick Edit buttons when selecting code", "选中代码时显示[添加到聊天]和[快速编辑]按钮"],

        // -- 内联编辑与终端 --
        ["Inline Editing & Terminal", "内联编辑与终端"],
        ["Cmd+K: Escape focuses the editor when you have a diff", "Cmd+K：有差异时按 Escape 聚焦编辑器"],
        ["Make escape focus editor instead of closing the prompt bar", "让 Escape 聚焦编辑器而不是关闭提示栏"],
        ["Terminal Hint", "终端提示"],
        ["Inline Diffs", "内联差异"],
        ["Show inline diff decorations in the editor instead of only showing changes in the review panel", "在编辑器中显示内联差异装饰，而不仅在审查面板中显示更改"],
        ["Themed Diff Backgrounds", "主题化差异背景"],
        ["Use themed background colors for inline code diffs", "为内联代码差异使用主题化背景颜色"],
        ["Jump to Next Diff on Accept", "接受后跳转到下一个差异"],

        // -- 通知声音 --
        ["Completion Sound", "完成提示音"],
        ["Play a sound when Agent finishes responding", "当 Agent 完成回复时播放提示音"],
        ["Notification Sound", "通知声音"],
        ["Reset to default sound", "重置为默认声音"],
        ["Default sound", "默认声音"],
        ["Browse...", "浏览..."],
        ["Failed to play sound. Please check the file path is valid and the file is a supported audio format (mp3, wav, ogg).", "播放声音失败。请检查文件路径是否有效，以及文件是否为受支持的音频格式（mp3、wav、ogg）。"],

        // -- 开发工具 --
        ["Development", "开发"],
        ["Enable Disposable Tracking", "启用一次性追踪"],
        ["Disposable Tracking", "一次性追踪"],
        ["Enable leak detection console output", "启用内存泄漏检测控制台输出"],
        ["Leak Detection", "内存泄漏检测"],
        ["Solid Dev Tools", "Solid 开发工具"],
        ["Enable Solid Dev Tools", "启用 Solid 开发工具"],
        ["Force View Zones", "强制显示视图区域"],
        ["Force the display of view zones in the editor", "强制在编辑器中显示视图区域"],
        ["Show view zone when preview box is clipped", "预览框被裁剪时显示视图区域"],
        ["Show a view zone when the preview box is clipped", "预览框被裁剪时显示视图区域"],
        ["Extension RPC Tracer", "扩展 RPC 追踪器"],
        ["Log extension host RPC messages to JSON files viewable in Perfetto for performance analysis. Requires a restart to take effect.", "将扩展宿主 RPC 消息记录到 JSON 文件中，可在 Perfetto 中查看以进行性能分析。需要重启才能生效。"],
        ["Optional folder for RPC logs (defaults to logs/exthost)", "RPC 日志的可选文件夹（默认为 logs/exthost）"],
        ["This action enables IDE debug log upload which contains information about IDE behavior itself and is required for bug investigations", "此操作启用 IDE 调试日志上传，其中包含有关 IDE 行为本身的信息，是调查 Bug 所必需的"],

        // -- 扩展安全 --
        ["Extension Security", "扩展安全"],
        ["Verify Extension Signatures", "验证扩展签名"],
        ["Verify extension signatures when installing and loading extensions", "安装和加载扩展时验证扩展签名"],

        // -- 隐藏对话框 --
        ["See warnings and tips that you\\u2019ve hidden", "查看您已隐藏的警告和提示"],
        ["No Hidden Dialogs Yet", "暂无隐藏的对话框"],
        ["Restore", "恢复"],

        // -- 开发登录 --
        ["Dev Login (Free)", "开发登录（免费版）"],
        ["Dev Login (Pro)", "开发登录（专业版）"],
        ["Dev Login (Pro Trial)", "开发登录（专业版试用）"],
        ["Dev Login (Pro Plus)", "开发登录（Pro Plus）"],
        ["Dev Login (Pro Plus Trial)", "开发登录（Pro Plus 试用）"],
        ["Dev Login (Enterprise)", "开发登录（企业版）"],
        ["Dev Login (Ultra)", "开发登录（Ultra）"],
        ["Login with Free for local development", "使用免费版登录进行本地开发"],
        ["Login with Pro plan for local development", "使用专业版登录进行本地开发"],
        ["Login with Pro Trial for local development", "使用专业版试用登录进行本地开发"],
        ["Login with Pro Plus for local development", "使用 Pro Plus 登录进行本地开发"],
        ["Login with Pro Plus Trial for local development", "使用 Pro Plus 试用登录进行本地开发"],
        ["Login with Enterprise (team) for local development", "使用企业版（团队）登录进行本地开发"],
        ["Login with Ultra plan for local development", "使用 Ultra 登录进行本地开发"],
        ["Enterprise Login", "企业版登录"],
        ["Free Login", "免费版登录"],
        ["Pro Login", "专业版登录"],
        ["Pro Plus Login", "Pro Plus 登录"],
        ["Pro Plus Trial Login", "Pro Plus 试用登录"],
        ["Pro Trial Login", "专业版试用登录"],
        ["Ultra Login", "Ultra 登录"],

        // ==================== 智能体 (Agents) 页面 ====================
        ["Auto-Run", "自动运行"],
        ["Auto-Run Mode", "自动运行模式"],
        ["Choose how Agent runs tools like command execution, MCP, and file writes.", "选择 Agent 如何运行工具（如命令执行、MCP 和文件写入）。"],
        ["Choose how Agent runs tools like command execution, MCP, and file writes", "选择 Agent 如何运行工具（如命令执行、MCP 和文件写入）"],
        ["Run Everything", "运行所有"],
        ["Run Everything (Unsandboxed)", "运行所有（无沙盒）"],
        ["Ask Every Time", "每次询问"],
        ["Auto-Run in Sandbox", "在沙盒中自动运行"],
        ["Use Allowlist", "使用白名单"],
        ["Auto-Approved Mode Transitions", "自动批准模式切换"],
        ["Mode transitions that will be automatically approved without prompting.", "将自动批准而无需提示的模式切换。"],
        ["Mode transitions that will be automatically approved without prompting", "将自动批准而无需提示的模式切换"],
        ["Browser Protection", "浏览器保护"],
        ["Prevent Agent from automatically running Browser tools", "阻止 Agent 自动运行浏览器工具"],
        ["MCP Tools Protection", "MCP 工具保护"],
        ["Prevent Agent from automatically running MCP tools", "阻止 Agent 自动运行 MCP 工具"],
        ["External-File Protection", "外部文件保护"],
        ["Prevent Agent from automatically editing files outside of the workspace", "阻止 Agent 自动编辑工作区外的文件"],
        ["File-Deletion Protection", "文件删除保护"],
        ["Prevent Agent from automatically deleting files", "阻止 Agent 自动删除文件"],
        ["Prevent Agent from deleting files automatically", "阻止 Agent 自动删除文件"],
        ["External-File Protection", "外部文件保护"],
        ["Prevent Agent from automatically editing files outside of the workspace", "阻止 Agent 自动编辑工作区外的文件"],
        ["Prevent Agent from creating or modifying files outside of the workspace automatically", "阻止 Agent 自动在工作区外创建或修改文件"],
        ["Default Location", "默认位置"],
        ["Where to open new agents", "新建智能体的打开位置"],
        ["Pane", "面板"],
        ["Window", "窗口"],
        ["Text Size", "文字大小"],
        ["Adjust the conversation text size", "调整对话文字大小"],
        ["Small", "小"],
        ["Large", "大"],
        ["Extra Large", "超大"],
        ["Auto-Clear Chat", "自动清除对话"],
        ["After periods of inactivity, open the Agent Pane to a new conversation", "闲置一段时间后，打开 Agent 面板时开始新对话"],
        ["Submit with Ctrl + Enter", "使用 Ctrl + Enter 提交"],
        ["When enabled, Ctrl + Enter submits chat and Enter inserts a newline", "启用后，Ctrl + Enter 提交对话，Enter 插入换行"],
        ["Max Tab Count", "最大标签页数"],
        ["Limit how many chat tabs can be open at once", "限制同时打开的对话标签页数量"],
        ["Queue Messages", "消息队列"],
        ["Send after current message", "在当前消息之后发送"],
        ["Stop & send right away", "停止并立即发送"],
        ["Adjust the default behavior of sending a message while Agent is running", "调整 Agent 运行时发送消息的默认行为"],
        ["Usage Summary", "用量摘要"],
        ["When to show the usage summary at the bottom of the chat pane", "何时在聊天面板底部显示用量摘要"],
        ["Always", "始终"],
        ["Never", "从不"],
        ["Auto", "自动"],
        ["Suggest Next Prompt", "建议下一个提示"],
        ["Suggest the next prompt for Agent", "为 Agent 建议下一个提示"],
        ["Contextual suggestions while prompting Agent", "在提示 Agent 时提供上下文建议"],
        ["Agent Autocomplete", "Agent 自动补全"],

        // -- 自动运行网络/沙盒 --
        ["Auto-Run Network Access", "自动运行网络访问"],
        ["Control which network requests are allowed when commands run in the sandbox.", "控制在沙盒中运行命令时允许哪些网络请求。"],
        ["Allow All", "全部允许"],
        ["sandbox.json + Defaults", "sandbox.json + 默认"],
        ["sandbox.json Only", "仅 sandbox.json"],
        ["Command Allowlist", "命令白名单"],
        ["Commands that can run automatically", "可以自动运行的命令"],
        ["Command Denylist", "命令黑名单"],
        ["Commands that should always require user approval, even if they match allowlist patterns", "即使匹配白名单模式，也应始终需要用户批准的命令"],
        ["Smart Allowlist", "智能白名单"],
        ["Use AI-powered command classification to intelligently match commands against allowlist patterns and suggest sandbox modes", "使用 AI 驱动的命令分类来智能匹配白名单模式并建议沙盒模式"],
        ["Choose how Agent runs tools like command execution, MCP, and file writes. Tools will auto-run in a sandbox if possible. If not, they will respect the allowlist or ask for approval.", "选择 Agent 如何运行工具（如命令执行、MCP 和文件写入）。如果可能，工具将在沙盒中自动运行。否则，它们将遵循白名单或请求批准。"],
        ["MCP Allowlist", "MCP 白名单"],
        ["MCP tools that can run automatically. Format: 'server:tool', 'server:*' for all tools from a server, '*:tool' for a tool from any server, or '*:*' for all tools from all servers", "可以自动运行的 MCP 工具。格式：'server:tool'、'server:*' 表示某服务器的所有工具、'*:tool' 表示任意服务器的某工具、'*:*' 表示所有服务器的所有工具"],

        // -- Agent 审查 --
        ["Agent Review", "Agent 审查"],
        ["Auto-Run On Agent Finish", "Agent 完成时自动运行"],
        ["Automatically review your changes for issues after each commit", "每次提交后自动审查更改中的问题"],
        ["Start Agent Review on Commit", "提交时启动 Agent 审查"],
        ["Include Submodules in Agent Review", "在 Agent 审查中包含子模块"],
        ["Include changes from Git submodules in the review", "在审查中包含 Git 子模块的更改"],
        ["Include Untracked Files in Agent Review", "在 Agent 审查中包含未跟踪文件"],
        ["Include untracked files (new files not yet added to Git) in the review", "在审查中包含未跟踪的文件（尚未添加到 Git 的新文件）"],
        ["Default Approach", "默认方式"],
        ["Choose between quick or more thorough, higher-cost analysis", "选择快速或更彻底、更高成本的分析"],
        ["Quick", "快速"],
        ["Deep", "深度"],
        ["Automatically run Review when Agent finishes and has made file changes", "当 Agent 完成并修改了文件时自动运行审查"],

        // -- 提交署名 --
        ["Attribution", "署名"],
        ["Commit Attribution", "提交署名"],
        ["Mark Agent commits as 'Made with Cursor'", "将 Agent 提交标记为'使用 Cursor 制作'"],
        ["PR Attribution", "PR 署名"],
        ["Mark pull requests as made with Cursor", "将拉取请求标记为使用 Cursor 制作"],
        ["Git", "Git"],
        ["Branch Prefix", "分支前缀"],
        ["Prefix for new branches created by Agent (e.g., cursor/, username/)", "Agent 创建新分支的前缀（例如：cursor/、username/）"],

        // -- 格式化 --
        ["Auto Format on Agent Finish", "Agent 完成时自动格式化"],
        ["Automatically format files when the agent finishes", "当智能体完成时自动格式化文件"],

        // -- 浏览器/声音 --
        ["Browser", "浏览器"],
        ["Browser Tab", "浏览器标签"],
        ["Show Localhost Links in Browser", "在浏览器中显示 Localhost 链接"],
        ["Automatically open localhost links in the Browser Tab", "自动在浏览器标签页中打开 localhost 链接"],
        ["Browser automation disabled", "浏览器自动化已禁用"],

        // -- 语音模式 --
        ["Voice Mode", "语音模式"],
        ["Submit Keywords", "提交关键词"],
        ["Custom keywords that trigger auto-submit in voice mode. Only single words (no spaces) are allowed. Punctuation and capitalization are ignored.", "在语音模式下触发自动提交的自定义关键词。仅允许单个词语（无空格）。忽略标点和大小写。"],

        // ==================== 代码补全 (Tab) 页面 ====================
        ["Cursor Tab", "Cursor Tab"],
        ["Enable Cursor Tab", "启用 Cursor Tab"],
        ["Context-aware, multi-line suggestions around your cursor based on recent edits", "基于最近编辑，围绕光标提供上下文感知的多行建议"],
        ["Cursor Prediction", "Cursor 预测"],
        ["Enable Cursor Prediction", "启用 Cursor 预测"],
        ["Partial Accepts", "部分接受"],
        ["Accept the next word of a suggestion via Ctrl+RightArrow", "通过 Ctrl+右箭头 接受建议的下一个词"],
        ["Suggestions While Commenting", "注释时的建议"],
        ["Allow Tab to trigger while in a comment region", "允许在注释区域中触发 Tab"],
        ["Whitespace-Only Suggestions", "仅空白建议"],
        ["Suggest edits like new lines and indentation that modify whitespace only", "建议仅修改空白的编辑，如新行和缩进"],
        ["Cpp Control Token", "Cpp 控制令牌"],
        ["Control tokens control how likely the model is to produce no-ops. Will be replaced with auto-selection", "控制令牌控制模型产生空操作的可能性。将被自动选择替代"],
        ["Auto-Import", "自动导入"],
        ["Imports", "导入"],
        ["Automatically import necessary modules for TypeScript", "自动为 TypeScript 导入必要的模块"],
        ["Enable auto import for Python. This is a beta feature.", "启用 Python 的自动导入。这是一个测试版功能。"],
        ["Auto Import for Python BETA", "Python 自动导入 测试版"],
        ["Auto-imports are temporarily disabled", "自动导入暂时已禁用"],
        ["CPP is temporarily disabled", "CPP 暂时已禁用"],
        ["CPP and auto-imports are temporarily disabled", "CPP 和自动导入暂时已禁用"],
        ["Ignored Files", "忽略的文件"],
        ["Glob patterns for files where Cursor Tab will not suggest", "Cursor Tab 不提供建议的文件 Glob 模式"],

        // ==================== 云端智能体 (Cloud Agents) 页面 ====================
        ["Cloud Agents Unavailable", "云端智能体不可用"],
        ["Cloud Agents require a Git repository in an open folder.", "云端智能体需要在打开的文件夹中有 Git 仓库。"],
        ["Open a Git repository", "打开 Git 仓库"],
        ["Loading Cloud Agents settings...", "正在加载云端智能体设置..."],
        ["GitHub Pull Requests", "GitHub Pull 请求"],
        ["Review PRs, fix CI, address comments, and more directly from Cursor", "直接在 Cursor 中审查 PR、修复 CI、回复评论等"],
        ["Connect Slack", "连接 Slack"],
        ["Accelerate development, shared knowledge, and context across your team", "加速开发，在团队中共享知识和上下文"],
        ["Work with Cloud Agents from Slack", "通过 Slack 使用云端智能体"],
        ["Connect GitHub/GitLab, manage team and user settings, and configure environments", "连接 GitHub/GitLab，管理团队和用户设置，配置环境"],
        ["Manage Settings", "管理设置"],
        ["Configured in the dashboard", "在控制面板中配置"],
        ["Team-Level Repository Control", "团队级别仓库控制"],
        ["Disable AI features in specific repositories based on file pattern", "基于文件模式在特定仓库中禁用 AI 功能"],

        // -- 本地自动化 --
        ["Local Automations", "本地自动化"],
        ["Run recurring agent tasks locally on this machine. Each automation can target a specific model.", "在本机上运行重复的智能体任务。每个自动化可以指定特定模型。"],
        ["New Automation", "新建自动化"],
        ["Automation name", "自动化名称"],
        ["Schedule", "调度"],
        ["Add Time", "添加时间"],
        ["Every day", "每天"],
        ["Weekdays", "工作日"],
        ["Mo", "一"],
        ["Tu", "二"],
        ["We", "三"],
        ["Th", "四"],
        ["Fr", "五"],
        ["Sa", "六"],
        ["Su", "日"],
        ["Create a Cloud Automation pre-filled with this local automation's settings", "使用此本地自动化的设置创建云端自动化"],
        ["No local automations yet. Create one to get started.", "暂无本地自动化。创建一个以开始使用。"],
        ["Loading local automations...", "正在加载本地自动化..."],
        ["Send to Cloud", "发送到云端"],
        ["Name is required.", "名称为必填项。"],
        ["Prompt is required.", "提示为必填项。"],
        ["Cron expression is required.", "Cron 表达式为必填项。"],
        ["Model: Auto", "模型：自动"],

        // ==================== 插件 (Plugins) 页面 ====================
        ["From plugins installed in Cursor", "来自 Cursor 中已安装的插件"],
        ["Include third-party Plugins, Skills, and other configs", "包含第三方插件、技能和其他配置"],
        ["Automatically import agent configs from other tools", "自动从其他工具导入智能体配置"],
        ["Browse Marketplace", "浏览市场"],
        ["Plugin MCP Servers", "插件 MCP 服务器"],
        ["Installed MCP Servers", "已安装的 MCP 服务器"],
        ["Remove local plugin", "移除本地插件"],

        // ==================== 规则、技能、子智能体页面 ====================
        ["User Rules", "用户规则"],
        ["Project Rules", "项目规则"],
        ["User Rule", "用户规则"],
        ["Project Rule", "项目规则"],
        ["User Command", "用户命令"],
        ["Project Command", "项目命令"],
        ["Add Rule", "添加规则"],
        ["Add rule", "添加规则"],
        ["Add new rule", "添加新规则"],
        ["Rules for AI", "AI 规则"],
        ["Use Rules to guide agent behavior, like enforcing best practices or coding standards. Rules can be applied always, by file path, or manually.", "使用规则来指导智能体行为，如强制执行最佳实践或编码标准。规则可以始终应用、按文件路径应用或手动应用。"],
        ["Create rules to guide Agent behavior", "创建规则来指导 Agent 行为"],
        ["Always applied", "始终应用"],
        ["Apply to Specific Files & Folders", "应用于特定文件和文件夹"],
        ["Agent decides when to apply", "Agent 决定何时应用"],
        ["No Rules Yet", "暂无规则"],
        ["Delete Rule", "删除规则"],
        ["Skills", "技能"],
        ["Provide domain-specific knowledge and workflows for the agent", "为智能体提供领域特定的知识和工作流"],
        ["Skills help the agent accomplish specific tasks", "技能帮助智能体完成特定任务"],
        ["Skills are specialized capabilities that help the agent accomplish specific tasks. Skills will be invoked by the agent when relevant or can be triggered manually with / in chat.", "技能是帮助智能体完成特定任务的专门能力。智能体会在相关时调用技能，也可以在聊天中使用 / 手动触发。"],
        ["No Skills Yet", "暂无技能"],
        ["New Skill", "新建技能"],
        ["Delete Skill", "删除技能"],
        ["Subagents", "子智能体"],
        ["Create specialized agents for complex tasks. Subagents can be invoked by the agent to handle focused work in parallel.", "为复杂任务创建专门的智能体。子智能体可以被智能体调用，以并行处理专注的工作。"],
        ["Create specialized agents to handle focused tasks", "创建专门的智能体来处理专注的任务"],
        ["No Subagents Yet", "暂无子智能体"],
        ["New Subagent", "新建子智能体"],
        ["Delete Subagent", "删除子智能体"],
        ["Commands", "命令"],
        ["Create commands to build reusable workflows", "创建命令以构建可复用的工作流"],
        ["Create reusable workflows triggered with / prefix in chat. Use commands to standardize processes and make common tasks more efficient.", "创建在聊天中使用 / 前缀触发的可复用工作流。使用命令来标准化流程，使常见任务更高效。"],
        ["No Commands Yet", "暂无命令"],
        ["New Command", "新建命令"],
        ["Delete Command", "删除命令"],
        ["Learn about Rules", "了解规则"],
        ["Learn about Skills", "了解技能"],
        ["Learn about Subagents", "了解子智能体"],
        ["Learn about Commands", "了解命令"],
        ["Learn about Hooks", "了解钩子"],
        ["Open JSON", "打开 JSON"],
        ["Open enterprise config", "打开企业版配置"],
        ["Open project config", "打开项目配置"],
        ["Open user config", "打开用户配置"],

        // ==================== 工具与 MCP 页面 ====================
        ["MCP Servers", "MCP 服务器"],
        ["MCP servers", "MCP 服务器"],
        ["Configure MCP servers in the dashboard to make them available in Cursor on desktop and in the cloud.", "在控制面板中配置 MCP 服务器，使其在桌面和云端的 Cursor 中可用。"],
        ["Team MCP Servers", "团队 MCP 服务器"],
        ["No Team MCP Servers", "暂无团队 MCP 服务器"],
        ["No MCP Tools", "暂无 MCP 工具"],
        ["Add MCP Server", "添加 MCP 服务器"],
        ["Delete MCP Server", "删除 MCP 服务器"],
        ["Tools", "工具"],
        ["Resources", "资源"],
        ["Prompts", "提示词"],
        ["Browser", "浏览器"],
        ["Browser Automation", "浏览器自动化"],
        ["Browser automation disabled", "浏览器自动化已禁用"],
        ["Home MCP Servers", "主页 MCP 服务器"],
        ["Servers available in this workspace.", "此工作区中可用的服务器。"],
        ["User MCP Servers", "用户 MCP 服务器"],
        ["No User MCP Tools", "暂无用户 MCP 工具"],
        ["Add a custom MCP tool here or configure project-specific tools", "在此添加自定义 MCP 工具，或配置项目专用工具"],
        ["Add a custom MCP tool here or configure project-specific tools in <project-root>/.cursor/mcp.json", "在此添加自定义 MCP 工具，或在 <project-root>/.cursor/mcp.json 中配置项目专用工具"],
        ["Add a custom MCP tool here", "在此添加自定义 MCP 工具"],
        ["or configure project-specific tools", "或配置项目专用工具"],
        ["Add a", "添加"],
        ["tool here", "工具"],
        ["in <project-root>/.cursor/mcp.json", "位置：<project-root>/.cursor/mcp.json"],
        ["in <project-root>/", "位置：<project-root>/"],
        [".cursor/mcp.json", ".cursor/mcp.json"],
        ["custom MCP tool", "自定义 MCP 工具"],
        ["project-specific tools", "项目专用工具"],
        ["Add a custom MCP tool in your user MCP config.", "在用户 MCP 配置中添加自定义 MCP 工具。"],
        ["Add Custom MCP", "添加自定义 MCP"],
        ["Configure Team MCP Servers", "配置团队 MCP 服务器"],
        ["Cursor Settings", "Cursor 设置"],
        ["Meet the new Agents Window", "认识全新的智能体窗口"],
        ["Agents Window", "智能体窗口"],
        ["Open Codex Sidebar", "打开 Codex 侧边栏"],
        ["Export Transcript", "导出对话记录"],
        ["Copy Request ID", "复制请求 ID"],
        ["Give Feedback", "提供反馈"],
        ["Agent Settings", "智能体设置"],
        ["Configure Icon Visibility", "配置图标可见性"],
        ["Jump back to the Agents Window to keep working across repos.", "返回智能体窗口以继续跨仓库工作。"],
        ["Switch to Agents Window", "切换到智能体窗口"],
        ["Meet the new Cursor", "认识全新的 Cursor"],
        ["Run Many Agents in Parallel", "并行运行多个智能体"],
        ["All your agents across repos—locally, on remote SSH, and in the cloud", "您的所有智能体都可跨仓库运行，可在本地、远程 SSH 和云端使用"],
        ["Dig Deeper Anytime", "随时深入探索"],
        ["Access the best parts of the editor when you need them, like files and browser", "在需要时访问编辑器中最好用的部分，例如文件和浏览器"],
        ["Run many agents in parallel — across repos, locally, on remote SSH, and in the cloud.", "并行运行多个智能体，可跨仓库、本地、远程 SSH 和云端。"],
        ["Try it now", "立即体验"],
        ["Open project", "打开项目"],
        ["Clone repo", "克隆仓库"],
        ["New Window", "新建窗口"],
        ["Recent projects", "最近项目"],
        ["Agent Window", "智能体窗口"],
        ["You can clone a repository locally.", "您可以在本地克隆一个仓库。"],
        ["To learn more about how to use Git and source control in VS Code read our docs.", "若想进一步了解如何在 VS Code 中使用 Git 和源代码管理，请阅读我们的文档。"],
        ["read our docs.", "阅读我们的文档。"],
        ["Window Layout", "窗口布局"],
        ["Switch between Agent and Editor default layouts", "在智能体和编辑器默认布局之间切换"],
        ["Auto-Approve Mode Transitions", "自动批准模式切换"],
        ["Allow Agent to switch modes without asking first, such as Agent to Plan or Agent to Debug. When off, Cursor asks before switching.", "允许智能体在不先询问的情况下切换模式，例如从智能体切换到计划模式或调试模式。关闭后，Cursor 会在切换前询问。"],
        ["Compact Terminal Tool Calls", "紧凑显示终端工具调用"],
        ["Show terminal commands in compact view by default", "默认以紧凑视图显示终端命令"],
        ["Explore subagent model", "Explore 子智能体模型"],
        ["The Explore subagent is used to do initial research for the main agent", "Explore 子智能体用于为主智能体做初步调研"],
        ["Enabled by Run Everything Auto-Run Mode: Agent bypasses approval prompts for tools including Web Search", "由“全部运行”自动运行模式启用：智能体会跳过包括网页搜索在内的工具审批提示"],

        // ==================== 钩子 (Hooks) 页面 ====================
        ["Hooks let you run custom scripts at specific points during the agent's execution to modify behavior, enforce policies, or add custom logging.", "钩子允许您在智能体执行的特定时间点运行自定义脚本，以修改行为、强制执行策略或添加自定义日志。"],
        ["Note that paths are relative to the hooks.json file", "注意路径相对于 hooks.json 文件"],
        ["Note that plugin hooks paths are relative to the plugin install path.", "注意插件钩子路径相对于插件安装路径。"],
        ["Configured Hooks", "已配置的钩子"],
        ["No hooks configured", "暂无已配置的钩子"],
        ["No hook executions yet", "暂无钩子执行记录"],
        ["Invalid hooks.json found", "发现无效的 hooks.json"],
        ["Error Output:", "错误输出："],
        ["Input:", "输入："],
        ["Output:", "输出："],
        ["Execution Log", "执行日志"],
        ["Clear log", "清除日志"],
        ["We detected a hooks.json file that could not be loaded. Fix the errors below to enable hooks.", "我们检测到一个无法加载的 hooks.json 文件。请修复下方错误以启用钩子。"],

        // ==================== 索引与文档 (Indexing & Docs) 页面 ====================
        ["Codebase", "代码库"],
        ["Codebase Indexing", "代码库索引"],
        ["Codebase indexing", "代码库索引"],
        ["Worktrees", "工作树"],
        ["Cleanup", "清理"],
        ["Cursor periodically removes old worktrees to free disk space. Tune how aggressively cleanup runs.", "Cursor 会定期移除旧工作树以释放磁盘空间。可调整清理执行的激进程度。"],
        ["Max worktrees", "最大工作树数量"],
        ["Maximum number of Cursor-managed worktrees to retain across all workspaces. Older worktrees are removed first.", "在所有工作区中保留的由 Cursor 管理的工作树最大数量。较旧的工作树会优先被移除。"],
        ["Max total size (GB)", "最大总大小（GB）"],
        ["Maximum total size in GB across all Cursor-managed worktrees. Set to 0 to disable the size limit.", "所有由 Cursor 管理的工作树的最大总大小（GB）。设为 0 可禁用大小限制。"],
        ["Cursor-managed worktrees", "Cursor 管理的工作树"],
        ["No Cursor-managed worktrees on this machine.", "这台机器上没有由 Cursor 管理的工作树。"],
        ["Learn about codebase indexing", "了解代码库索引"],
        ["Codebase Index deleted", "代码库索引已删除"],
        ["Delete Codebase Index?", "删除代码库索引？"],
        ["Delete Index", "删除索引"],
        ["Index New Folders", "索引新文件夹"],
        ["Index Repositories for Instant Grep", "索引仓库以实现即时搜索"],
        ["Automatically index repositories to speed up Grep searches. All data is stored locally.", "自动索引仓库以加速 Grep 搜索。所有数据都存储在本地。"],
        ["Embed codebase for improved contextual understanding and knowledge", "嵌入代码库以提高上下文理解和知识"],
        ["Embed codebase for improved contextual understanding and knowledge.", "嵌入代码库以提高上下文理解和知识。"],
        ["Embeddings and metadata are stored in the cloud, but all code is stored locally.", "嵌入向量和元数据存储在云端，但所有代码都存储在本地。"],
        ["Embeddings and metadata are stored in the", "嵌入向量和元数据存储在"],
        ["cloud", "云端"],
        [", but all code is stored locally.", "，但所有代码都存储在本地。"],
        ["Embeddings and metadata are stored in the cloud, but all code is stored locally", "嵌入向量和元数据存储在云端，但所有代码都存储在本地"],
        ["but all code is stored locally.", "但所有代码都存储在本地。"],
        ["Files to exclude from indexing in addition to .gitignore.", "除 .gitignore 外要从索引中排除的文件。"],
        ["View included files.", "查看包含的文件。"],
        ["Compute index", "计算索引"],
        ["Pause Indexing", "暂停索引"],
        ["Paused", "已暂停"],
        ["Embedding Model", "嵌入模型"],
        ["Select your preferred embedding model. Delete your index and reload to use it.", "选择您首选的嵌入模型。删除索引并重新加载以使用它。"],
        ["Context", "上下文"],
        ["Hierarchical Cursor Ignore", "分层 Cursor 忽略"],
        ["Apply .cursorignore files to all subdirectories. Changing this setting will require a restart of Cursor.", "将 .cursorignore 文件应用到所有子目录。更改此设置需要重启 Cursor。"],
        ["Ignore Files in .cursorignore", "忽略 .cursorignore 中的文件"],
        ["Ignore Symlinks in Cursor Ignore Search", "在 Cursor 忽略搜索中忽略符号链接"],
        ["Use with caution. Skip symlinks during .cursorignore file discovery. Only enable if your repository has many symlinks and all .cursorignore files are reachable without them. Changing this setting will require a restart of Cursor.", "谨慎使用。在 .cursorignore 文件发现期间跳过符号链接。仅在您的仓库有很多符号链接且所有 .cursorignore 文件无需它们即可访问时启用。更改此设置需要重启 Cursor。"],
        ["Configure Ignored Files", "配置忽略的文件"],
        ["Auto-Accept Web Search", "自动接受网络搜索"],
        ["Allow Agent to search the web for relevant information", "允许 Agent 搜索网络以获取相关信息"],
        ["Auto-Parse Links", "自动解析链接"],
        ["Automatically parse links when pasted into Quick Edit (Ctrl+K) input", "粘贴到快速编辑（Ctrl+K）输入时自动解析链接"],
        ["Auto Jump to Next Diff", "自动跳到下一个差异"],
        ["Automatically jump to the next diff when accepting changes with Ctrl+Y", "使用 Ctrl+Y 接受更改时自动跳到下一个差异"],
        ["Auto Format After Agent Finishes", "Agent 完成后自动格式化"],
        ["Automatically format changed files when Agent finishes", "当 Agent 完成时自动格式化已更改文件"],
        ["Terminal Hints", "终端提示"],
        ["Show a hint for Ctrl+K in the Terminal", "在终端中显示 Ctrl+K 提示"],
        ["Preview Box for Terminal Ctrl+K", "终端 Ctrl+K 预览框"],
        ["Use a preview box instead of directly streaming into the Shell", "使用预览框，而不是直接流式传输到 Shell 中"],
        ["Allow Agent to fetch content from URLs", "允许 Agent 从 URL 获取内容"],
        ["Crawl and index custom resources and developer docs", "爬取和索引自定义资源和开发者文档"],
        ["Add Doc", "添加文档"],
        ["Add documentation to use as context. You can also use @Add in Chat or while editing to add a doc.", "添加文档用作上下文。您还可以在聊天中或编辑时使用 @Add 来添加文档。"],
        ["No Docs Added", "暂无已添加的文档"],
        ["Indexing", "索引"],
        ["Automatically", "自动"],
        ["Automatically index any new folders", "自动索引新增文件夹"],
        ["Automatically index any new folders with fewer than 50,000 files", "自动索引文件数少于 50,000 的新增文件夹"],
        ["index any new folders with fewer than 50,000 files", "索引文件数少于 50,000 的新增文件夹"],
        ["index any new folders", "索引新增文件夹"],
        ["with fewer than 50,000 files", "当文件数少于 50,000 个时"],
        ["Embed codebase for improved contextual understanding and knowledge. Embeddings and metadata are stored in the cloud, but all code is stored locally.", "嵌入代码库以提高上下文理解和知识。嵌入向量和元数据存储在云端，但所有代码都存储在本地。"],

        // ==================== 插件 (Plugins) 页面 ====================
        ["Plugins", "插件"],
        ["Extend Cursor with Skills, Rules, Agents, Hooks, and MCPs", "通过技能、规则、智能体、钩子和 MCP 扩展 Cursor"],
        ["Search or Paste Link", "搜索或粘贴链接"],
        ["Suggested", "推荐"],
        ["MCPs", "MCP"],
        ["No Plugins", "暂无插件"],
        ["Browse the marketplace or import custom plugins to extend", "浏览市场或导入自定义插件来扩展"],
        ["Cursor with Skills, Rules, Agents, Hooks, and MCPs.", "Cursor，并为其添加技能、规则、智能体、钩子和 MCP。"],
        ["Cursor with Skills, Rules, Agents, Hooks, and MCPs", "Cursor，并为其添加技能、规则、智能体、钩子和 MCP"],
        ["Browse the marketplace or import custom plugins to extend Cursor with Skills, Rules, Agents, Hooks, and MCPs", "浏览市场或导入自定义插件，通过技能、规则、智能体、钩子和 MCP 扩展 Cursor"],
        ["Browse the marketplace or import custom plugins to extend Cursor with Skills, Rules, Agents, Hooks, and MCPs.", "浏览市场或导入自定义插件，通过技能、规则、智能体、钩子和 MCP 扩展 Cursor。"],
        ["Add Plugin", "添加插件"],

        // ==================== 网络 (Network) 页面 ====================
        ["HTTP Compatibility Mode", "HTTP 兼容模式"],
        ["HTTP/2", "HTTP/2"],
        ["HTTP/1.1", "HTTP/1.1"],
        ["HTTP/1.0", "HTTP/1.0"],
        ["HTTP/2 is recommended for low-latency streaming. In some corporate proxy and VPN environments, the compatibility mode may need to be lowered.", "建议使用 HTTP/2 以实现低延迟流式传输。在某些企业代理和 VPN 环境中，可能需要降低兼容模式。"],
        ["Network Diagnostics", "网络诊断"],
        ["Check network connectivity to all Cursor services", "检查与所有 Cursor 服务的网络连接"],
        ["Required Domains", "必需域名"],
        ["These domains must be accessible for Cursor to function. Add them to your firewall or proxy allowlist.", "这些域名必须可访问才能让 Cursor 正常工作。请将它们添加到防火墙或代理白名单中。"],
        ["Fetch Domain Allowlist", "域名获取白名单"],
        ["Domains that Agent can fetch from automatically. Use '*' for all domains, '*.example.com' for wildcard subdomains.", "Agent 可以自动获取的域名。使用 '*' 表示所有域名，'*.example.com' 表示通配子域名。"],
        ["Copy results", "复制结果"],
        ["Copied", "已复制"],
        ["Show Logs", "显示日志"],
        ["Hide Logs", "隐藏日志"],

        // ==================== 测试版 (Beta) 页面 ====================
        ["Background Agents", "后台 Agent"],
        ["Bug Finder", "Bug 查找器"],
        ["Bug finder", "Bug 查找器"],
        ["Invite Team Members", "邀请团队成员"],
        ["Invite teammates", "邀请队友"],
        ["Invite", "邀请"],

        // ==================== 模型 (Models) 页面 ====================
        ["API Key", "API 密钥"],
        ["API Keys", "API 密钥"],
        ["Base URL", "基础 URL"],
        ["Override OpenAI Base URL", "覆盖 OpenAI 基础 URL"],
        ["Change the base URL for OpenAI API requests.", "更改 OpenAI API 请求的基础 URL。"],
        ["OpenAI API Key", "OpenAI API 密钥"],
        ["Anthropic API Key", "Anthropic API 密钥"],
        ["Google API Key", "Google API 密钥"],
        ["Azure OpenAI", "Azure OpenAI"],
        ["AWS Bedrock", "AWS Bedrock"],
        ["Deployment Name", "部署名称"],
        ["Region", "区域"],
        ["Access Key ID", "访问密钥 ID"],
        ["Secret Access Key", "秘密访问密钥"],
        ["Add Model", "添加模型"],
        ["Add model", "添加模型"],
        ["Remove Model", "移除模型"],
        ["Remove model", "移除模型"],
        ["Test Model", "测试模型"],
        ["DeepSeek V4 Pro", "DeepSeek V4 Pro"],
        ["Add or search model", "添加或搜索模型"],
        ["Enter model name", "输入模型名称"],
        ["Enter your OpenAI API Key", "输入您的 OpenAI API 密钥"],
        ["Enter your Anthropic API Key", "输入您的 Anthropic API 密钥"],
        ["Enter your Google AI Studio API Key", "输入您的 Google AI Studio API 密钥"],
        ["Enter your Azure OpenAI API Key", "输入您的 Azure OpenAI API 密钥"],
        ["You can put in your OpenAI key to use OpenAI models at cost.", "您可以填写自己的 OpenAI key 来按成本价使用 OpenAI 模型。"],
        ["You can put in your Anthropic key to use Claude at cost. When enabled, this key will be used for all models beginning with claude-.", "您可以填写自己的 Anthropic key 来按成本价使用 Claude。启用后，此 key 将用于所有以 claude- 开头的模型。"],
        ["You can put in your Google AI Studio key to use Google models at-cost.", "您可以填写自己的 Google AI Studio key 来按成本价使用 Google 模型。"],
        ["Configure Azure OpenAI to use OpenAI models through your Azure account.", "配置 Azure OpenAI，通过您的 Azure 账户使用 OpenAI 模型。"],
        ["Configure AWS Bedrock to use Anthropic Claude models through your AWS account.", "配置 AWS Bedrock，通过您的 AWS 账户使用 Anthropic Claude 模型。"],
        ["Cursor Enterprise teams can configure IAM roles to access Bedrock without any Access Keys.", "Cursor Enterprise 团队可配置 IAM 角色，无需任何 Access Keys 即可访问 Bedrock。"],
        ["Turn Off Anthropic Key", "关闭 Anthropic 密钥"],
        ["Turn Off Google Key", "关闭 Google 密钥"],
        ["Select Custom Chime Sound", "选择自定义提示音"],
        ["Legacy Terminal Tool", "旧版终端工具"],
        ["Use the legacy terminal tool in agent mode, for use on systems with unsupported shell configurations", "在智能体模式下使用旧版终端工具，适用于不支持的 Shell 配置系统"],
        ["Use a preview box instead of streaming responses directly into the shell", "使用预览框而不是将响应直接流式传输到 Shell 中"],
        ["Collapse Auto-Run Commands", "折叠自动运行命令"],
        ["Collapse auto-run command output by default in Terminal command previews", "在终端命令预览中默认折叠自动运行命令输出"],
        ["Always respond in Chinese-simplified", "始终以简体中文回复"],
        ["Open Web Links in Browser", "在浏览器中打开网页链接"],
        ["Automatically open http and https links in the Browser Tab", "自动在浏览器标签页中打开 http 和 https 链接"],
        ["Workbench › Cloud Changes: Auto Resume", "工作台 › 云端更改：自动恢复"],
        ["Workbench › Cloud Changes: Continue Prompt", "工作台 › 云端更改：继续提示"],
        ["Workbench › Experimental › Cloud Changes: Auto Store", "工作台 › 实验性 › 云端更改：自动存储"],
        ["Workbench › Experimental › Cloud Changes › Partial Matches: Enabled", "工作台 › 实验性 › 云端更改 › 部分匹配：已启用"],
        ["Workbench › Settings: Enable Natural Language Search", "工作台 › 设置：启用自然语言搜索"],

        // ==================== 工作区设置 / 终端 (Workspace / Terminal) ====================
        ["Terminal › Explorer Kind", "终端 › 资源管理器类型"],
        ["When opening a file from the Explorer in a terminal, determines what kind of terminal will be launched", "当从资源管理器在终端中打开文件时，决定将启动哪种类型的终端"],
        ["Terminal › Integrated: Accessible View Focus On Command Execution", "终端 › 集成：命令执行时聚焦可访问视图"],
        ["On command execution, focus the accessible view of the terminal.", "执行命令时，将焦点放在终端的可访问视图上。"],
        ["Terminal › Integrated: Accessible View Preserve Cursor Position", "终端 › 集成：可访问视图保留光标位置"],
        ["Whether to preserve the cursor position when reopening the terminal's accessible view rather than setting it to the bottom of the buffer.", "重新打开终端的可访问视图时，是否保留光标位置，而不是将其设为缓冲区底部。"],
        ["Terminal › Integrated: Allow Chords", "终端 › 集成：允许组合键"],
        ["Whether to allow chord keybindings in the terminal. Note that when this is true and the chord is a terminal command, the command to skip shell is ignored. This is useful to disable chord keybindings that conflict with shell bindings such as ctrl+k.", "是否允许在终端中使用组合键绑定。请注意，当该值为 true 且该组合键是终端命令时，将忽略“命令跳过 Shell”。这对于禁用与 Shell 绑定冲突的组合键（例如 ctrl+k）很有用。"],
        ["Terminal › Integrated: Allowed Link Schemes", "终端 › 集成：允许的链接方案"],
        ["An array of strings containing URI schemes allowed to be activated from the terminal. By default, only a small subset of potentially safe schemes is allowed.", "包含允许从终端中激活的 URI 方案的字符串数组。默认情况下，仅允许一小部分可能安全的方案。"],
        ["Terminal › Integrated: Allow Mnemonics", "终端 › 集成：允许助记键"],
        ["Whether to allow mnemonics for menu items to run in the terminal, for example Alt+F opens the File menu. This will cause all alt keystrokes to skip the shell when true. This does nothing on macOS.", "是否允许菜单项助记键在终端中生效，例如 Alt+F 打开“文件”菜单。启用后，所有 Alt 按键都会跳过 Shell。此设置在 macOS 上不起作用。"],
        ["Terminal › Integrated: Alt Click Moves Cursor", "终端 › 集成：Alt+单击移动光标"],
        ["Whether holding a modifier key and clicking in the terminal will move the cursor position. The effective behavior is determined by the editor.multiCursorModifier setting value. This setting can be used to disable this behavior.", "在终端中按住修饰键并单击时，是否移动光标位置。实际行为由 editor.multiCursorModifier 的设置值决定。此设置可用于禁用该行为。"],
        ["If enabled, when editor.multiCursorModifier is set to 'alt', alt/option+click will reposition the cursor under the mouse. The option is not available on macOS because alt is used to insert special characters in the terminal.", "如果启用，当 editor.multiCursorModifier 设置为 'alt'（默认值）时，alt/option+单击会将光标移动到鼠标下方。该选项在 macOS 上不可用，因为 alt 用于在终端中输入特殊字符。"],
        ["Terminal › Integrated › Automation Profile: Linux", "终端 › 集成 › 自动化配置文件：Linux"],
        ["The terminal profile to use on Linux for automation-related terminal usage like tasks and debug.", "在 Linux 上用于任务、调试等自动化相关终端场景的终端配置文件。"],
        ["Terminal › Integrated: Command To Skip Shell", "终端 › 集成：跳过 Shell 的命令"],
        ["Terminal › External: Linux Exec", "终端 › 外部：Linux 可执行程序"],
        ["Terminal › External: Osx Exec", "终端 › 外部：macOS 可执行程序"],
        ["Terminal › External: Windows Exec", "终端 › 外部：Windows 可执行程序"],
        ["Customizes which terminal to run on Linux.", "自定义在 Linux 上运行的终端程序。"],
        ["Customizes which terminal application to run on macOS.", "自定义在 macOS 上运行的终端应用程序。"],
        ["Customizes which terminal to run on Windows.", "自定义在 Windows 上运行的终端程序。"],
        ["Terminal › Integrated: Rescale Overlapping Glyphs", "终端 › 集成：重新缩放重叠字形"],
        ["Whether to rescale glyphs that are scaled down to fit a single cell with overlapping glyphs from the next cell. This is primarily intended to handle ambiguous width characters such as U+2160 and box-drawing characters that can overlap. This will never rescale Emoji.", "是否重新缩放那些被压缩到单个单元格内、且与下一个单元格字形重叠的字形。此项主要用于处理 U+2160 等模糊宽度字符以及可能发生重叠的制表符号/框线字符。该选项不会重新缩放 Emoji。"],
        ["Terminal › Integrated: Right Click Behavior", "终端 › 集成：右键点击行为"],
        ["Controls how terminal responds to right click.", "控制终端如何响应右键点击操作。"],
        ["Terminal › Integrated: Scrollback", "终端 › 集成：回滚缓冲区"],
        ["Controls the maximum number of lines the terminal keeps in its buffer.", "控制终端在其缓冲区中保留的最大行数。"],
        ["We pre-allocate memory based on this value in order to ensure a smooth experience. As such, as the value increases, so will the amount of memory.", "我们会根据此值预分配内存，以确保流畅体验。因此，随着该值增加，内存占用也会增加。"],
        ["Terminal › Integrated: Send Keybindings To Shell", "终端 › 集成：将键绑定发送到 Shell"],
        ["Dispatches most keybindings to the terminal instead of the workbench, overriding commands like terminal.focusNextPane. This can be useful for advanced shell usage.", "将大多数键绑定发送到终端而不是工作台，并覆盖诸如 terminal.focusNextPane 之类的命令。这对高级 Shell 使用场景会很有用。"],
        ["Terminal › Integrated › Tabs: Enable Animation", "终端 › 集成 › 选项卡：启用动画"],
        ["Controls whether terminal tabs show animations in states like running tasks.", "控制终端选项卡状态是否支持动画（例如正在进行的任务）。"],
        ["Terminal › Integrated › Tabs: Enabled", "终端 › 集成 › 选项卡：已启用"],
        ["Controls whether terminal tabs display as a list to the side of the terminal. When disabled, this will show a dropdown.", "控制终端选项卡是否以列表的形式显示在终端的一侧。如果禁用此功能，将改为显示下拉列表。"],
        ["Terminal › Integrated › Tabs: Focus Mode", "终端 › 集成 › 选项卡：聚焦模式"],
        ["Controls whether to focus a tab on hover, single click or double click.", "控制是在双击时将焦点放在某个选项卡上还是单击。"],
        ["Terminal › Integrated › Tabs: Hide Condition", "终端 › 集成 › 选项卡：隐藏条件"],
        ["Controls whether to hide the terminal tabs view under certain conditions.", "控制在特定条件下是否将隐藏终端选项卡视图。"],
        ["Terminal › Integrated › Tabs: Location", "终端 › 集成 › 选项卡：位置"],
        ["Controls the location of the terminal tabs, either to the left or right of the actual terminal.", "控制终端选项卡的位置，该位置位于实际终端的左侧或右侧。"],
        ["Terminal › Integrated › Tabs: Separator", "终端 › 集成 › 选项卡：分隔符"],
        ["The separator used for the terminal.integrated.tabs.title and terminal.integrated.tabs.description.", "terminal.integrated.tabs.title 和 terminal.integrated.tabs.description 使用的分隔符。"],
        ["Terminal › Integrated › Tabs: Show Actions", "终端 › 集成 › 选项卡：显示操作"],
        ["Controls whether to show the actions for the active terminal in the tab row.", "控制是否在“新建终端”按钮旁边显示“终端拆分”和“终止”按钮。"],
        ["Terminal › Integrated › Tabs: Show Active Terminal", "终端 › 集成 › 选项卡：显示活动终端"],
        ["Controls whether to show the active terminal when there is only a single terminal in the terminal tabs list.", "控制当终端标签列表中只有一个终端时，是否显示活动终端。"],
        ["Terminal › Integrated › Tabs: Stop Width", "终端 › 集成 › 选项卡：制表位宽度"],
        ["Terminal › Integrated: Text Blinking", "终端 › 集成：文本闪烁"],
        ["Controls whether text blinking is enabled in the terminal.", "控制终端中的文本闪烁是否已启用。"],
        ["Terminal › Integrated: Unicode Version", "终端 › 集成：Unicode 版本"],
        ["Controls the version of Unicode to use when measuring the width of characters in the terminal. If you experience emoji or other wide characters either taking up too much or too little space, you may want to tweak this setting.", "控制在终端中计算字符宽度时要使用的 Unicode 版本。如果遇到未占用正确空格或退格量的表情符号或其他宽字符，或删除量太大或太小，则可能希望尝试调整此设置。"],
        ["Terminal › Integrated: Use Wsl Profiles", "终端 › 集成：使用 WSL 配置文件"],
        ["Controls whether to show WSL distros in the terminal dropdown.", "控制是否在终端下拉列表中显示 WSL 发行版"],
        ["Terminal › Integrated: Windows Enable Conpty", "终端 › 集成：Windows 启用 ConPTY"],
        ["Whether to use ConPTY for Windows terminal process communication (requires Windows 10 build number 18309+). When this is false, Winpty will be used.", "是否使用 ConPTY 进行 Windows 终端进程通信（需要 Windows 10 内部版本号 18309+）。如果此设置为 false，将使用 Winpty。"],
        ["Terminal › Integrated: Windows Use Conpty Dll", "终端 › 集成：Windows 使用 ConPTY DLL"],
        ["Whether to use the VS Code provided experimental conpty.dll instead of the one bundled with Windows.", "是否使用 VS Code 附带的，而不是与 Windows 捆绑的实验性 conpty.dll。"],
        ["Terminal › Integrated: Word Separators", "终端 › 集成：单词分隔符"],
        ["A string containing all characters that should be considered word separators when doing word related navigations and operations. Since this is used for link detection, characters such as `.` that are used for link paths should not be considered word separators.", "一个包含所有字符的字符串，在双击选择单词和回退“word”键接检测时，会被视为单词分隔符。由于这用于链接检测，包括在检测链接时使用“.”之类的字符，将会忽略诸如 file:10.5 等链接的行和列部分。"],
        ["Terminal › Source Control Repositories Kind", "终端 › 源代码管理仓库类型"],
        ["When opening a repository from the Source Control Repositories view in a terminal, determines what kind of terminal will be launched", "当从“源代码管理仓库”视图在终端中打开仓库时，决定将启动哪种类型的终端"],
        ["Terminal › Integrated › Shell Integration: Decorations", "终端 › 集成 › Shell 集成：装饰"],
        ["Enable decorations for each command when shell integration is enabled.", "启用 shell 集成后，为每个命令显示装饰。"],
        ["Terminal › Integrated › Shell Integration: Enabled", "终端 › 集成 › Shell 集成：已启用"],
        ["Controls whether to automatically inject shell integration to support features like enhanced command tracking and current working directory detection.", "控制是否自动注入 shell 集成，以支持增强命令跟踪、当前工作目录检测等功能。"],
        ["Shell integration works by injecting a script that makes VS Code aware of what is happening in the terminal.", "Shell 集成通过注入脚本来工作，使 VS Code 能够了解终端中正在发生的情况。"],
        ["Supported shells:", "支持的 shell："],
        ["Accessible View", "可访问视图"],
        ["Allow Chords", "允许组合键"],
        ["Allowed Link Schemes", "允许的链接方案"],
        ["Allow Mnemonics", "允许助记键"],
        ["Alt Click Moves Cursor", "Alt+单击移动光标"],
        ["Automation Profile", "自动化配置文件"],
        ["Explorer", "资源管理器"],
        ["Integrated", "集成"],
        ["Kind", "类型"],

        // ==================== 通用 UI 元素 ====================
        ["Save", "保存"],
        ["Cancel", "取消"],
        ["Delete", "删除"],
        ["Edit", "编辑"],
        ["Add", "添加"],
        ["Remove", "移除"],
        ["Create", "创建"],
        ["Reset", "重置"],
        ["Reset All", "全部重置"],
        ["Apply", "应用"],
        ["Close", "关闭"],
        ["Search", "搜索"],
        ["Search models", "搜索模型"],
        ["Settings", "设置"],
        ["Preferences", "首选项"],
        ["Configuration", "配置"],
        ["Configure", "配置"],
        ["Edit configuration", "编辑配置"],
        ["Configuration Errors", "配置错误"],
        ["Enable", "启用"],
        ["Disable", "禁用"],
        ["On", "开"],
        ["Off", "关"],
        ["OK", "确定"],
        ["Yes", "是"],
        ["No", "否"],
        ["None", "无"],
        ["All", "全部"],
        ["Default", "默认"],
        ["Custom", "自定义"],
        ["More", "更多"],
        ["Less", "更少"],
        ["Show", "显示"],
        ["Hide", "隐藏"],
        ["Copy", "复制"],
        ["Open", "打开"],
        ["New", "新建"],
        ["Preview", "预览"],
        ["Submit", "提交"],
        ["Confirm", "确认"],
        ["Continue", "继续"],
        ["Back", "返回"],
        ["Next", "下一步"],
        ["Previous", "上一步"],
        ["Done", "完成"],
        ["Loading...", "加载中..."],
        ["Loading", "加载中"],
        ["Retry", "重试"],
        ["Learn more", "了解更多"],
        ["Learn More", "了解更多"],
        ["Dismiss", "关闭"],
        ["Install", "安装"],
        ["Installed", "已安装"],
        ["Uninstall", "卸载"],
        ["Update", "更新"],
        ["Explore", "探索"],
        ["Popular", "热门"],
        ["Trending", "趋势"],
        ["Name", "名称"],
        ["Value", "值"],
        ["Key", "键"],
        ["Status", "状态"],
        ["Actions", "操作"],
        ["Warning", "警告"],
        ["Info", "信息"],
        ["Error", "错误"],
        ["Success", "成功"],
        ["Failed", "失败"],
        ["Pending", "等待中"],
        ["Active", "活动"],
        ["Running", "运行中"],
        ["Syncing", "同步中"],
        ["Initializing", "初始化中"],
        ["Sync", "同步"],
        ["Restart", "重启"],
        ["Download", "下载"],
        ["Import", "导入"],
        ["Export", "导出"],
        ["Applying Changes", "正在应用更改"],
        ["No description", "无描述"],
        ["Get Started", "开始使用"],
        ["Create with Agent", "使用 Agent 创建"],
        ["Editor Window", "编辑器窗口"],
        ["Home", "主页"],
        ["Local", "本地"],
        ["No Local Changes", "没有本地更改"],
        ["Uncommitted", "未提交"],
        ["Unstaged", "未暂存"],
        ["Staged", "已暂存"],
        ["All commits", "所有提交"],
        ["Use a Git repository to track changes", "使用 Git 仓库来跟踪更改"],
        ["Initialize Repository", "初始化仓库"],
        ["Connect GitHub", "连接 GitHub"],
        ["Connect GitHub to create, update, and merge pull requests directly in Cursor.", "连接 GitHub，以便直接在 Cursor 中创建、更新和合并拉取请求。"],
        ["Unified", "统一视图"],
        ["Split", "拆分视图"],
        ["Ignore Whitespace", "忽略空白字符"],
        ["Find in Diff", "在差异中查找"],
        ["Refresh Changes", "刷新更改"],
        ["User", "用户"],
        ["Agent", "智能体"],
        ["Changes", "更改"],
        ["Files", "文件"],
        ["Terminal", "终端"],
        ["Zoom In", "放大"],
        ["Zoom Out", "缩小"],
        ["Reset Zoom", "重置缩放"],
        ["Mark All as Read", "全部标记为已读"],
        ["Mark All Read", "全部标记为已读"],
        ["Mark as Unread", "标记为未读"],
        ["Archive All", "全部归档"],
        ["Archive", "归档"],
        ["Remove from Sidebar", "从侧边栏移除"],
        ["Group by", "分组方式"],
        ["Workspace", "工作区"],
        ["Repository", "仓库"],
        ["Updated", "更新时间"],
        ["Environment", "环境"],
        ["Collapse All", "全部折叠"],
        ["Pin", "固定"],
        ["Rename", "重命名"],
        ["Fork Chat", "分叉对话"],
        ["Unread", "未读"],
        ["Archived", "已归档"],
        ["Unread, Archived", "未读、已归档"],
        ["Only Unread", "仅未读"],
        ["Only Archived", "仅已归档"],
        ["Include Archived", "包含已归档"],
        ["Show Machine Label", "显示机器标签"],
        ["Show Icon", "显示图标"],
        ["Draft", "草稿"],
        ["Needs Attention", "需要关注"],
        ["Merged", "已合并"],
        ["Closed", "已关闭"],
        ["No PR", "无 PR"],
        ["Cloud", "云端"],
        ["This PC", "此电脑"],
        ["Desktop", "桌面端"],
        ["Web", "网页端"],
        ["SCM", "源代码管理"],
        ["CLI", "命令行"],
        ["Setup", "设置向导"],
        ["SDK", "开发工具包"],
        ["Automations", "自动化"],
        ["Source", "来源"],
        ["Metadata", "元数据"],
        ["Search Tool", "搜索工具"],
        ["Fetch Tool", "抓取工具"],
        ["Web Search Tool", "网页搜索工具"],
        ["Web Fetch Tool", "网页抓取工具"],
        ["Cursor Auth Debug", "Cursor 认证调试"],
        ["Cursor Agent Exec", "Cursor 智能体执行"],
        ["Cursor Agent Review", "Cursor 智能体审查"],
        ["Cursor Agent Worker", "Cursor 智能体工作器"],
        ["Cursor Always Local", "Cursor 始终本地"],
        ["Cursor Git Graph", "Cursor Git 图谱"],
        ["Cursor Grep Service", "Cursor Grep 服务"],
        ["Cursor IDE Browser Automation", "Cursor IDE 浏览器自动化"],
        ["Cursor Indexing & Retrieval", "Cursor 索引与检索"],
        ["Cursor Plugins", "Cursor 插件"],
        ["Cursor Resolver Helper", "Cursor 解析助手"],
        ["Cursor Socket", "Cursor Socket"],
        ["MCP Logs", "MCP 日志"],
        ["MCP OAuth", "MCP OAuth"],
        ["Mcp FileSystem Writer", "MCP 文件系统写入器"],
        ["Filesync", "文件同步"],
        ["Bugbot Autofix", "Bugbot 自动修复"],
        ["Frontend QA", "前端质检"],
        ["Run Cursor anywhere...", "在任意位置运行 Cursor..."],
        ["Recents", "最近使用"],
        ["Set Up Workspace", "设置工作区"],
        ["Open Project", "打开项目"],
        ["Clone Repository", "克隆仓库"],
        ["Connect via SSH", "通过 SSH 连接"],
        ["Connect SSH", "连接 SSH"],
        ["Connect WSL", "连接 WSL"],
        ["Try a new window for running parallel agents", "打开新窗口来并行运行多个智能体"],
        ["Split Right", "向右拆分"],
        ["Split Down", "向下拆分"],
        ["New Worktree", "新建工作树"],
        ["Plan New Idea", "规划新想法"],
        ["Plan New Idea ⇧ Tab", "规划新想法 ⇧ Tab"],
        ["MAX Mode", "MAX 模式"],
        ["Efficiency", "效率"],
        ["Premium Intelligence", "高级智能"],
        ["Add Models", "添加模型"],
        ["Fast", "快速"],
        ["Conversation Density", "对话密度"],
        ["Choose how much detail Agent tool calls show in the conversation", "选择在对话中显示多少智能体工具调用细节"],
        ["Compact", "紧凑"],
        ["Balanced", "均衡"],
        ["Detailed", "详细"],
        ["Status Bar", "状态栏"],
        ["Show status bar at the bottom", "在底部显示状态栏"],
        ["Review Location", "审查位置"],
        ["Panel", "面板"],
        ["Sidebar", "侧边栏"],
        ["Editor", "编辑器"],
        ["Editor auto-hides when empty", "编辑器为空时自动隐藏"],
        ["When all editors are closed, hide the editor area and maximize chat", "当所有编辑器关闭时，隐藏编辑器区域并最大化聊天"],
        ["Show chat in editor tabs", "在编辑器标签页中显示对话"],
        ["Show chat in editor tabs in the chat area instead of the old stacked view", "在聊天区域中以编辑器标签页显示对话，而不是旧的堆叠视图"],
        ["System Notifications", "系统通知"],
        ["Show system notifications when Agent completes or needs attention", "当智能体完成或需要关注时显示系统通知"],
        ["System Tray Icon", "系统托盘图标"],
        ["Show Cursor in the system tray", "在系统托盘中显示 Cursor"],
        ["Completion Sound", "完成提示音"],
        ["Play a sound when Agent completes or needs attention", "当智能体完成或需要关注时播放提示音"],
        ["10", "10"],
        ["All Files", "所有文件"],
        ["Audio Files", "音频文件"],
        ["Breadcrumb", "面包屑"],
        ["Island", "浮动岛"],
        ["Start Free Trial", "开始免费试用"],
        ["Start free trial", "开始免费试用"],
        ["Marketplace", "市场"],
        ["Market", "市场"],
        ["Featured", "精选"],
        ["Infrastructure", "基础设施"],
        ["Data & Analytics", "数据与分析"],
        ["Productivity", "生产力"],
        ["Payments", "支付"],
        ["Agent Orchestration", "智能体编排"],
        ["Canvas", "画布"],
        ["All Plugins", "全部插件"],
        ["Documentation", "文档"],
        ["Get", "获取"],
        ["Add to Cursor", "添加到 Cursor"],
        ["Skills", "技能"],
        ["Search skills, rules, subagents, MCPs, and hooks", "搜索技能、规则、子智能体、MCP 和钩子"],

        // ==================== 菜单栏 (Menu Bar) ====================
        ["File", "文件"],
        ["New Agent", "新建智能体"],
        ["Open Folder", "打开文件夹"],
        ["New Text File", "新建文本文件"],
        ["New Window", "新建窗口"],
        ["New Agents Window", "新建智能体窗口"],
        ["Open File...", "打开文件..."],
        ["Open Folder...", "打开文件夹..."],
        ["Open Workspace from File...", "从文件打开工作区..."],
        ["Open Recent", "打开最近的文件"],
        ["Add Folder to Workspace...", "将文件夹添加到工作区..."],
        ["Save Workspace As...", "将工作区另存为..."],
        ["Duplicate Workspace", "复制工作区"],
        ["Close Window", "关闭窗口"],
        ["New Terminal", "新建终端"],
        ["New Browser", "新建浏览器"],
        ["Open Editor Window", "打开编辑器窗口"],
        ["Exit", "退出"],
        ["Undo", "撤销"],
        ["Redo", "重做"],
        ["Cut", "剪切"],
        ["Paste", "粘贴"],
        ["Select All", "全选"],
        ["Open Changes", "打开更改"],
        ["Open Browser", "打开浏览器"],
        ["Open File", "打开文件"],
        ["Open Terminal", "打开终端"],
        ["Help", "帮助"],
        ["Command Palette", "命令面板"],
        ["View License", "查看许可证"],

        // ==================== Command Palette ====================
        ["Search files, actions, agents...", "搜索文件、操作、智能体..."],
        ["Plan, Build, / for commands, @ for context", "计划、构建，输入 / 调用命令，输入 @ 添加上下文"],
        ["Help me create this skill for Cursor!", "帮我为 Cursor 创建这个技能！"],
        ["Use Voice", "使用语音"],
        ["Pin / Unpin Agent", "固定/取消固定智能体"],
        ["Go Back", "返回"],
        ["Go Forward", "前进"],
        ["Plan Mode", "计划模式"],
        ["Ask Mode", "询问模式"],
        ["Debug Mode", "调试模式"],
        ["Open Marketplace", "打开市场"],
        ["Toggle Full Screen", "切换全屏"],
        ["Mode", "模式"],
        ["View", "视图"],

        // ==================== placeholder 翻译 ====================
        ["AWS Access Key ID", "AWS 访问密钥 ID"],
        ["AWS Secret Access Key", "AWS 秘密访问密钥"]
    ]);

    var MoShi_FanYi = [
        [/^(\\d+) requests? remaining$/i, "$1 次请求剩余"],
        [/^(\\d+) of (\\d+) requests?$/i, "$1 / $2 次请求"],
        [/^(\\d+) premium requests?$/i, "$1 次高级请求"],
        [/^(\\d+) files? indexed$/i, "$1 个文件已索引"],
        [/^Indexing (\\d+) files?$/i, "正在索引 $1 个文件"],
        [/^(\\d+) errors?$/i, "$1 个错误"],
        [/^(\\d+) warnings?$/i, "$1 个警告"],
        [/^Version (.+)$/i, "版本 $1"],
        [/^(\\d+) tools?$/i, "$1 个工具"],
        [/^(\\d+) resources?$/i, "$1 个资源"],
        [/^(\\d+) prompts?$/i, "$1 个提示词"],
        [/^Skills? (\\d+)$/i, "技能 $1"],
        [/^(\\d+) skills?$/i, "$1 个技能"],
        [/^No Local Changes$/i, "没有本地更改"],
        [/^(\\d+) Local Changes$/i, "$1 个本地更改"],
        [/^(\\d+) Changes$/i, "$1 个更改"],
        [/^Composer (.+) Fast$/i, "Composer $1 快速"],
        [/^Editor Window\\s*↗?$/i, "编辑器窗口 ↗"],
        [/^Plan New Idea\\s*⇧?\\s*Tab$/i, "规划新想法 ⇧ Tab"],
        [/^Resets on (.+)$/i, "将于 $1 重置"],
        [/^(.+)% Auto and (.+)% API used$/i, "$1% Auto 已用，$2% API 已用"],
        [/^Unlock Agent (.+)x usage and more$/i, "解锁 Agent $1 倍用量及更多"],
        [/^Updated (.+) ago$/i, "$1前更新"],
        [/^(\\d+) seconds? ago$/i, "$1 秒前"],
        [/^(\\d+) minutes? ago$/i, "$1 分钟前"],
        [/^(\\d+) hours? ago$/i, "$1 小时前"],
        [/^(\\d+) days? ago$/i, "$1 天前"],
        [/^Auto-Run Mode Disabled by Team Admin$/i, "自动运行模式已被团队管理员禁用"],
        [/^Auto-Run Mode Controlled by Team Admin$/i, "自动运行模式由团队管理员控制"],
        [/^Auto-Run Mode Controlled by Team Admin \\(Sandbox Enabled\\)$/i, "自动运行模式由团队管理员控制（沙盒已启用）"],
        [/^Enabled by Run Everything Auto-Run Mode:\s*Agent bypasses approval prompts for tools including Web Search\.?$/i, "由“全部运行”自动运行模式启用：智能体会跳过包括网页搜索在内的工具审批提示"],
        [/^Jump back to the Agents Window to keep working across repos\.?$/i, "返回智能体窗口以继续跨仓库工作。"],
        [/^Custom cron: (.+)$/i, "自定义 Cron：$1"],
        [/^(.+) at (.+)$/i, "$1 于 $2"],
        [/^Automatically index any new folders with fewer than (\\d+) files$/i, "自动索引文件数少于 $1 的新文件夹"],
        [/^Embed codebase for improved contextual understanding and knowledge\.\s*Embeddings and metadata are stored in the cloud, but all code is stored locally\.?$/i, "嵌入代码库以提高上下文理解和知识。嵌入向量和元数据存储在云端，但所有代码都存储在本地。"],
        [/^Use with caution\.\s*Skip symlinks during\s*\.?cursorignore file discovery\.\s*Only enable if your repository has many\s*symlinks and all\s*\.?cursorignore files are reachable without them\.\s*Changing this setting will require a restart of\s*Cursor\.?$/i, "谨慎使用。在 .cursorignore 文件发现期间跳过符号链接。仅在您的仓库有很多符号链接且所有 .cursorignore 文件无需它们即可访问时启用。更改此设置需要重启 Cursor。"],
        [/^(\\d+) hooks?$/i, "$1 个钩子"],
        [/^(\\d+) automations?$/i, "$1 个自动化"],
        [/^(\\d+) rules?$/i, "$1 条规则"],
        [/^(\\d+) commands?$/i, "$1 个命令"],
        [/^(\\d+) subagents?$/i, "$1 个子智能体"]
    ];

    // ================================================================
    // SECTION 2: 翻译引擎
    // ================================================================

    var TiaoGuo_XuanZeQi = '.monaco-editor, .overflow-guard, .view-lines, .editor-scrollable, .inputarea, .rename-input, .explorer-viewlet, [id="workbench.view.explorer"]';
    var TiaoGuo_BiaoQian = new Set(['TEXTAREA', 'INPUT', 'SCRIPT', 'STYLE', 'CODE', 'PRE', 'NOSCRIPT']);

    function GuiYiHua_WenBen(text) {
        return text.replace(/\s+/g, ' ').trim();
    }

    function ChaZhao_FanYi(text) {
        if (!text) return null;

        var trimmed = text.trim();
        var normalized = GuiYiHua_WenBen(text);

        if (FanYi_CiDian.has(trimmed)) return FanYi_CiDian.get(trimmed);
        if (normalized !== trimmed && FanYi_CiDian.has(normalized)) return FanYi_CiDian.get(normalized);

        for (var i = 0; i < MoShi_FanYi.length; i++) {
            var pair = MoShi_FanYi[i];
            if (pair[0].test(trimmed)) return trimmed.replace(pair[0], pair[1]);
            if (normalized !== trimmed && pair[0].test(normalized)) return normalized.replace(pair[0], pair[1]);
        }

        return null;
    }

    function TiHuan_BuFen_WenBen(text) {
        if (!text) return null;

        var result = text;
        var changed = false;
        var normalized = GuiYiHua_WenBen(text);
        var DingXiang_SuiPian = [
        ['Embed codebase for improved contextual understanding and knowledge.', '嵌入代码库以提升上下文理解与知识检索。'],
        ['Embed codebase for improved contextual understanding and knowledge', '嵌入代码库以提升上下文理解与知识检索'],
        ['Automatically index any new folders with fewer than 50,000 files', '自动索引文件数少于 50,000 的新增文件夹'],
        ['Embeddings and metadata are stored in the ', '嵌入向量和元数据存储在'],
            ['Embeddings and metadata are stored in ', '嵌入向量和元数据存储在'],
            [', but all code is stored locally.', '，但所有代码都存储在本地。'],
            ['but all code is stored locally.', '但所有代码都存储在本地。'],
            ['Auto Resume', '自动恢复'],
            ['Continue Prompt', '继续提示'],
            ['Auto Store', '自动存储'],
            ['Partial Matches', '部分匹配'],
            ['Natural Language Search', '自然语言搜索'],
            ['Natural Language 搜索', '自然语言搜索'],
            ['Automation Profile', '自动化配置文件'],
            ['Focus on Command Execution', '命令执行时聚焦'],
            ['Preserve Cursor Position', '保留光标位置']
        ];

        if (/^[a-z][\w-]*(?:\.[A-Za-z][\w-]*){1,}$/i.test(text)) {
            return null;
        }

        for (var i = 0; i < DingXiang_SuiPian.length; i++) {
            var pair = DingXiang_SuiPian[i];
            var neo = result.split(pair[0]).join(pair[1]);
            if (neo !== result) { result = neo; changed = true; }
        }

        for (var i = 0; i < MoShi_FanYi.length; i++) {
            var pair = MoShi_FanYi[i];
            if (pair[0].test(result)) {
                result = result.replace(pair[0], pair[1]);
                changed = true;
            }
        }

        if (changed) return result;

        result = normalized;
        for (var i = 0; i < DingXiang_SuiPian.length; i++) {
            var pair = DingXiang_SuiPian[i];
            var neo = result.split(pair[0]).join(pair[1]);
            if (neo !== result) { result = neo; changed = true; }
        }

        for (var i = 0; i < MoShi_FanYi.length; i++) {
            var pair = MoShi_FanYi[i];
            if (pair[0].test(result)) {
                result = result.replace(pair[0], pair[1]);
                changed = true;
            }
        }

        return changed ? result : null;
    }

    function FanYi_WenBen_JieDian(node) {
        var text = node.textContent;
        if (!text) return;
        var trimmed = text.trim();
        if (!trimmed || trimmed.length > 500) return;
        if (/^[\\d\\s.,;:!?@#$%^&*()\\-+=<>\\/\\\\|~`'"[\\]{}]+$/.test(trimmed)) return;

        var result = ChaZhao_FanYi(text);
        if (result) {
            var prefix = text.substring(0, text.indexOf(trimmed));
            var suffix = text.substring(text.indexOf(trimmed) + trimmed.length);
            node.textContent = prefix + result + suffix;
            return;
        }

        var partial = TiHuan_BuFen_WenBen(text);
        if (partial) node.textContent = partial;
    }

    function FanYi_ShuXing(el) {
        var attrs = ['title', 'aria-label', 'placeholder'];
        for (var i = 0; i < attrs.length; i++) {
            var val = el.getAttribute(attrs[i]);
            if (val) {
                var result = ChaZhao_FanYi(val);
                if (result) {
                    el.setAttribute(attrs[i], result);
                } else {
                    var partial = TiHuan_BuFen_WenBen(val);
                    if (partial) el.setAttribute(attrs[i], partial);
                }
            }
        }
    }

    function Shi_BianJiQi_QuYu(node) {
        var el = node.nodeType === Node.TEXT_NODE ? node.parentElement : node;
        if (!el) return true;
        if (TiaoGuo_BiaoQian.has(el.tagName)) return true;
        try { if (el.closest(TiaoGuo_XuanZeQi)) return true; } catch (e) {}
        return false;
    }

    function FanYi_ZiShu(root) {
        var stack = [root];
        while (stack.length > 0) {
            var node = stack.pop();
            if (node.nodeType === Node.ELEMENT_NODE) {
                if (TiaoGuo_BiaoQian.has(node.tagName)) continue;
                if (node.classList && (node.classList.contains('monaco-editor') || node.classList.contains('overflow-guard') || node.classList.contains('view-lines') || node.classList.contains('editor-scrollable'))) continue;
                if (node.getAttribute('contenteditable') === 'true') continue;
                if (node.id === 'cursor-yongliang-xianshi') continue;
                FanYi_ShuXing(node);
                var children = node.childNodes;
                for (var i = children.length - 1; i >= 0; i--) { stack.push(children[i]); }
            } else if (node.nodeType === Node.TEXT_NODE) {
                if (!Shi_BianJiQi_QuYu(node)) { FanYi_WenBen_JieDian(node); }
            }
        }
    }

    var DaiChuLi_JieDian = [];
    var YiDiaoDu = false;
    var ZhengZaiPiLiangFanYi = false;
    var QuanJuXiuZheng_YiPaiDui = false;
    var ShangCiQuanJuXiuZheng = 0;

    function TianJia_DaiChuLi(node) {
        DaiChuLi_JieDian.push(node);
        if (!YiDiaoDu) {
            YiDiaoDu = true;
            requestAnimationFrame(ZhiXing_PiLiang_FanYi);
        }
    }

    function PaiDui_QuanJuXiuZheng() {
        if (QuanJuXiuZheng_YiPaiDui) return;
        QuanJuXiuZheng_YiPaiDui = true;
        var now = Date.now();
        var delay = now - ShangCiQuanJuXiuZheng < 1200 ? 1200 : 450;
        setTimeout(function() {
            ShangCiQuanJuXiuZheng = Date.now();
            QuanJuXiuZheng_YiPaiDui = false;
            ZhengZaiPiLiangFanYi = true;
            try { XiuZheng_SuoYin_ShuoMing(); } catch (e) {}
            try { XiuZheng_DaiMaKu_ShuoMing(); } catch (e) {}
            try { XiuZheng_MoXing_Ye(); } catch (e) {}
            try { XiuZheng_SheZhi_SuiPian(); } catch (e) {}
            try { XiuZheng_ShiChang_FanYi(); } catch (e) {}
            try { GengXin_ShiChang_QieHuan_AnNiu(); } catch (e) {}
            try { ChaRu_YongLiang_XianShi(); } catch (e) {}
            ZhengZaiPiLiangFanYi = false;
        }, 300);
    }

    function ZhiXing_PiLiang_FanYi() {
        var nodes = DaiChuLi_JieDian;
        DaiChuLi_JieDian = [];
        YiDiaoDu = false;
        ZhengZaiPiLiangFanYi = true;
        try {
            for (var i = 0; i < nodes.length; i++) {
                try { FanYi_ZiShu(nodes[i]); } catch (e) {}
            }
        } finally {
            ZhengZaiPiLiangFanYi = false;
        }
        PaiDui_QuanJuXiuZheng();
    }

    function GuanCha_HuiDiao(mutations) {
        if (ZhengZaiPiLiangFanYi) return;
        for (var i = 0; i < mutations.length; i++) {
            var m = mutations[i];
            if (m.type === 'childList') {
                var added = m.addedNodes;
                for (var j = 0; j < added.length; j++) {
                    var node = added[j];
                    if (node.nodeType === Node.ELEMENT_NODE || node.nodeType === Node.TEXT_NODE) {
                        TianJia_DaiChuLi(node);
                    }
                }
            }
        }
    }

    function KeYi_AnQuan_GaiXie_WenBen(el, text, needles) {
        if (!el || !text) return false;
        if (text.length > 400) return false;
        try {
            if (el.querySelector('input, textarea, select, button, [role="button"], [role="switch"], [contenteditable="true"]')) return false;
        } catch (e) {}
        var parent = el.parentElement;
        if (parent) {
            var parentText = GuiYiHua_WenBen(parent.textContent || '');
            if (parentText && parentText !== text) {
                var parentHasAll = true;
                for (var i = 0; i < needles.length; i++) {
                    if (parentText.indexOf(needles[i]) === -1) {
                        parentHasAll = false;
                        break;
                    }
                }
                if (parentHasAll) return false;
            }
        }
        el.textContent = text;
        return true;
    }

    var QuanJuWenBen_HuanCun = { time: 0, text: '' };
    function HuoQu_QuanJu_WenBen() {
        var now = Date.now();
        if (now - QuanJuWenBen_HuanCun.time < 600) return QuanJuWenBen_HuanCun.text;
        var text = '';
        try { text = document.body ? GuiYiHua_WenBen(document.body.textContent || '') : ''; } catch (e) {}
        QuanJuWenBen_HuanCun.time = now;
        QuanJuWenBen_HuanCun.text = text;
        return text;
    }

    function QuanJu_BaoHan_GuanJianCi(words) {
        var text = HuoQu_QuanJu_WenBen();
        if (!text) return false;
        for (var i = 0; i < words.length; i++) {
            if (text.indexOf(words[i]) !== -1) return true;
        }
        return false;
    }

    function TiHuan_WenBenJieDian_SuiPian(root, fragments) {
        if (!root || !fragments || !fragments.length) return false;
        var changed = false;
        var walker;
        try {
            walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
        } catch (e) {
            return false;
        }

        var node;
        while ((node = walker.nextNode())) {
            if (Shi_BianJiQi_QuYu(node)) continue;
            var neo = node.textContent || '';
            for (var i = 0; i < fragments.length; i++) {
                neo = neo.split(fragments[i][0]).join(fragments[i][1]);
            }
            if (neo !== node.textContent) {
                node.textContent = neo;
                changed = true;
            }
        }
        return changed;
    }

    function XiuZheng_DaiMaKu_ShuoMing() {
        if (!QuanJu_BaoHan_GuanJianCi(['Embed codebase', 'Embeddings and metadata', '代码库索引', '索引新文件夹'])) return;
        var fragments = [
            ['Embed codebase for improved contextual understanding and knowledge.', '嵌入代码库以提升上下文理解与知识检索。'],
            ['Embed codebase for improved contextual understanding and knowledge', '嵌入代码库以提升上下文理解与知识检索'],
            ['Embeddings and metadata are stored in the ', '嵌入向量和元数据存储在'],
            ['Embeddings and metadata are stored in ', '嵌入向量和元数据存储在'],
            [', but all code is stored locally.', '，但所有代码都存储在本地。'],
            ['but all code is stored locally.', '但所有代码都存储在本地。']
        ];

        var all = document.querySelectorAll('div, span, p, label');
        for (var i = 0; i < all.length; i++) {
            var el = all[i];
            var text = GuiYiHua_WenBen(el.textContent || '');
            if (!text) continue;

            if (
                text.indexOf('Embed codebase for improved contextual understanding and knowledge') !== -1 ||
                text.indexOf('Embeddings and metadata are stored in') !== -1 ||
                (text.indexOf('嵌入代码库') !== -1 && text.indexOf('Embeddings and metadata') !== -1)
            ) {
                TiHuan_WenBenJieDian_SuiPian(el, fragments);
            }
        }
    }

    function XiuZheng_SuoYin_ShuoMing() {
        if (!QuanJu_BaoHan_GuanJianCi(['50,000 files', 'index any new folders', '索引新文件夹'])) return;
        var all = document.querySelectorAll('div, span, p, label');
        for (var i = 0; i < all.length; i++) {
            var el = all[i];
            var text = GuiYiHua_WenBen(el.textContent || '');
            if (!text) continue;

            if (
                text.indexOf('with fewer than 50,000 files') !== -1 ||
                text.indexOf('index any new folders') !== -1 ||
                text.indexOf('Automatically index any new folders') !== -1 ||
                text.indexOf('自动matically') !== -1
            ) {
                KeYi_AnQuan_GaiXie_WenBen(el, '自动索引文件数少于 50,000 的新增文件夹', ['index any new folders', '50,000']);
            }
        }
    }

    function XiuZheng_MoXing_Ye() {
        if (!QuanJu_BaoHan_GuanJianCi(['OpenAI key', 'Anthropic key', 'Google AI Studio key', 'Azure OpenAI', 'AWS Bedrock', 'DeepSeek'])) return;
        var all = document.querySelectorAll('div, span, p, label');
        for (var i = 0; i < all.length; i++) {
            var el = all[i];
            var text = GuiYiHua_WenBen(el.textContent || '');
            if (!text) continue;

            if (text.indexOf('深度Seek V4 Pro') !== -1) {
                el.textContent = el.textContent.replace(/深度Seek V4 Pro/g, 'DeepSeek V4 Pro');
                continue;
            }

            if (text.indexOf('OpenAI key') !== -1 && text.indexOf('OpenAI models') !== -1) {
                KeYi_AnQuan_GaiXie_WenBen(el, '您可以填写自己的 OpenAI key 来按成本价使用 OpenAI 模型。', ['OpenAI key', 'OpenAI models']);
                continue;
            }
            if (text.indexOf('Anthropic key') !== -1 && text.indexOf('beginning with') !== -1) {
                KeYi_AnQuan_GaiXie_WenBen(el, '您可以填写自己的 Anthropic key 来按成本价使用 Claude。启用后，此 key 将用于所有以 claude- 开头的模型。', ['Anthropic key', 'beginning with']);
                continue;
            }
            if (text.indexOf('Google AI Studio key') !== -1 && text.indexOf('Google models') !== -1) {
                KeYi_AnQuan_GaiXie_WenBen(el, '您可以填写自己的 Google AI Studio key 来按成本价使用 Google 模型。', ['Google AI Studio key', 'Google models']);
                continue;
            }
            if (text.indexOf('Configure Azure OpenAI') !== -1 && text.indexOf('Azure account') !== -1) {
                KeYi_AnQuan_GaiXie_WenBen(el, '配置 Azure OpenAI，通过您的 Azure 账户使用 OpenAI 模型。', ['Configure Azure OpenAI', 'Azure account']);
                continue;
            }
            if (text.indexOf('Configure AWS Bedrock') !== -1 && text.indexOf('AWS account') !== -1) {
                KeYi_AnQuan_GaiXie_WenBen(el, '配置 AWS Bedrock，通过您的 AWS 账户使用 Anthropic Claude 模型。', ['Configure AWS Bedrock', 'AWS account']);
                continue;
            }
            if (text.indexOf('Cursor Enterprise teams') !== -1 && text.indexOf('Access Keys') !== -1) {
                KeYi_AnQuan_GaiXie_WenBen(el, 'Cursor Enterprise 团队可配置 IAM 角色，无需任何 Access Keys 即可访问 Bedrock。', ['Cursor Enterprise teams', 'Access Keys']);
                continue;
            }
        }
    }

    function XiuZheng_SheZhi_SuiPian() {
        if (!QuanJu_BaoHan_GuanJianCi(['Automation Profile', 'Natural Language Search', 'Auto Resume', 'Partial Matches', 'Continue Prompt', '自动mation'])) return;
        var all = document.querySelectorAll('div, span, p, label');
        for (var i = 0; i < all.length; i++) {
            var el = all[i];
            var text = GuiYiHua_WenBen(el.textContent || '');
            if (!text) continue;

            if (/^[a-z][\w-]*(?:\.[A-Za-z][\w-]*){1,}$/i.test(text)) {
                continue;
            }

            if (text.indexOf('自动mation Profile') !== -1) {
                el.textContent = el.textContent.replace(/自动mation Profile/g, '自动化配置文件');
            }
            if (text.indexOf('Focus 开 Command Execution') !== -1) {
                el.textContent = el.textContent.replace(/Focus 开 Command Execution/g, '命令执行时聚焦');
            }
            if (text.indexOf('Preserve Cursor Position') !== -1) {
                el.textContent = el.textContent.replace(/Preserve Cursor Position/g, '保留光标位置');
            }
            if (text.indexOf('Natural Language 搜索') !== -1) {
                el.textContent = el.textContent.replace(/Natural Language 搜索/g, '自然语言搜索');
            }
            if (text.indexOf('Auto Resume') !== -1) {
                el.textContent = el.textContent.replace(/Auto Resume/g, '自动恢复');
            }
            if (text.indexOf('Auto Store') !== -1) {
                el.textContent = el.textContent.replace(/Auto Store/g, '自动存储');
            }
            if (text.indexOf('Partial Matches') !== -1) {
                el.textContent = el.textContent.replace(/Partial Matches/g, '部分匹配');
            }
            if (text.indexOf('Continue Prompt') !== -1) {
                el.textContent = el.textContent.replace(/Continue Prompt/g, '继续提示');
            }
        }
    }

    var ShiChang_FanYi_Jian = 'cursor_hanhua_market_translate';
    var ShiChang_FanYi_Kai = true;
    try { ShiChang_FanYi_Kai = localStorage.getItem(ShiChang_FanYi_Jian) !== '0'; } catch (e) {}
    var ShiChang_ZaiXianFanYi_Kai = false;
    try { ShiChang_ZaiXianFanYi_Kai = localStorage.getItem('cursor_hanhua_market_online_translate') === '1'; } catch (e) {}
    var ShiChang_Ye_HuanCun = { time: 0, value: false };
    var ShiChang_ZaiXianFanYi_BenLun = 0;

    var ShiChang_ChaJian_MingCheng = {
        'Datadog': '监控观测',
        'Slack': '团队协作',
        'Figma': '设计协作',
        'Linear': '项目管理',
        'Twilio': '通信服务',
        'Vantage': '云成本管理',
        'Azure': '微软云',
        'Temporal': '工作流编排',
        'typescript-lsp': 'TypeScript 语言服务',
        'terraform': 'Terraform 基础设施',
        'telegram': 'Telegram 通知',
        'swift-lsp': 'Swift 语言服务',
        'skill-creator': '技能创建器',
        'session-report': '会话报告',
        'serena': '语义代码分析',
        'security-guidance': '安全指导',
        'rust-analyzer-lsp': 'Rust 语言服务',
        'ruby-lsp': 'Ruby 语言服务',
        'ralph-loop': '自循环实验',
        'pyright-lsp': 'Python 语言服务',
        'pr-review-toolkit': 'PR 评审工具包',
        'plugin-dev': '插件开发工具包',
        'playwright': '浏览器自动化',
        'playground': '交互式演示',
        'php-lsp': 'PHP 语言服务',
        'mcp-server-dev': 'MCP 服务开发'
    };

    var ShiChang_JiNeng_MingCheng = {
        'ddconfig': '配置 Datadog',
        'ddsetup': '初始化 Datadog',
        'ddtoolsets': '管理 Datadog 工具集',
        'session-report': '生成会话报告',
        'skill-creator': '创建技能',
        'plugin-dev': '插件开发',
        'security-guidance': '安全指导',
        'frontend-qa': '前端质检'
    };

    var ShiChang_MingCheng_CiGen = {
        'typescript': 'TypeScript',
        'javascript': 'JavaScript',
        'swift': 'Swift',
        'rust': 'Rust',
        'ruby': 'Ruby',
        'php': 'PHP',
        'python': 'Python',
        'pyright': 'Python',
        'terraform': 'Terraform',
        'telegram': 'Telegram',
        'playwright': 'Playwright',
        'azure': 'Azure',
        'security': '安全',
        'guidance': '指导',
        'plugin': '插件',
        'plugins': '插件',
        'dev': '开发',
        'server': '服务',
        'creator': '创建器',
        'report': '报告',
        'session': '会话',
        'review': '评审',
        'toolkit': '工具包',
        'tool': '工具',
        'mcp': 'MCP',
        'lsp': '语言服务',
        'analyzer': '分析器',
        'browser': '浏览器',
        'automation': '自动化',
        'playground': '演示环境',
        'loop': '循环',
        'guidance': '指导'
    };

    var ShiChang_ZaiXianFanYi_Zhong = new Set();

    var ShiChang_MiaoShu_SuiPian = [
        ['Generate an explorable HTML report of Claude Code session usage', '生成可浏览的 Claude Code 会话用量 HTML 报告'],
        ['Generate an explorable HTML rep', '生成可浏览的 HTML 报告'],
        ['Generate an explor', '生成可浏览的'],
        ['tokens, cache efficiency, subagents, skills, and the most expensive prompts', '包括 token、缓存效率、子智能体、技能以及最昂贵的提示词'],
        ['from local ~/.claude/projects transcripts.', '数据来自本地 ~/.claude/projects 转录记录。'],
        ['TypeScript/JavaScript language server', 'TypeScript/JavaScript 语言服务器'],
        ['TypeScript/JavaScript language ser', 'TypeScript/JavaScript 语言服务器'],
        ['TypeScript/JavaScript language se', 'TypeScript/JavaScript 语言服务器'],
        ['Swift language server', 'Swift 语言服务器'],
        ['Swift language serv', 'Swift 语言服务器'],
        ['Rust language server', 'Rust 语言服务器'],
        ['Rust language serv', 'Rust 语言服务器'],
        ['Ruby language server', 'Ruby 语言服务器'],
        ['Ruby language serv', 'Ruby 语言服务器'],
        ['Python language server', 'Python 语言服务器'],
        ['Python language se', 'Python 语言服务器'],
        ['PHP language server', 'PHP 语言服务器'],
        ['language server for code intelligence', '用于代码智能的语言服务器'],
        ['language server for code inte', '用于代码智能的语言服务器'],
        ['for enhanced code intelligence', '用于增强代码智能'],
        ['enhanced code intelligence', '增强代码智能'],
        ['Semantic code analysis MCP server', '语义代码分析 MCP 服务器'],
        ['Semantic code analysis MCP serve', '语义代码分析 MCP 服务器'],
        ['Semantic code analysis MCP serve...', '语义代码分析 MCP 服务器...'],
        ['Use Datadog directly in Cursor through a preconfigured Datadog MCP server.', '通过预配置的 Datadog MCP 服务器直接在 Cursor 中使用 Datadog。'],
        ['Use Datadog directly in Cursor through a preconfigured Datadog MCP server', '通过预配置的 Datadog MCP 服务器直接在 Cursor 中使用 Datadog'],
        ['Query logs, metrics, traces, dashboards, and more through natural conversation.', '通过自然语言对话查询日志、指标、链路追踪、仪表盘等内容。'],
        ['This plugin is in preview.', '此插件处于预览阶段。'],
        ['Slack MCP server.', 'Slack MCP 服务器。'],
        ['Search channels, send messages, and perform operations', '搜索频道、发送消息并执行操作'],
        ['Search channels, send messages', '搜索频道、发送消息'],
        ['Plugin that includes the Figma MCP server and Skills for common', '包含 Figma MCP 服务器和常用技能的插件'],
        ['Cursor Plugin for Linear', 'Linear 的 Cursor 插件'],
        ['enables AI assistants to manage issues', '让 AI 助手能够管理议题'],
        ['Twilio Skills and MCP provide procedural knowledge for AI coding', 'Twilio 技能和 MCP 为 AI 编码提供流程化知识'],
        ['Twilio Skills and MCP provide procedural knowledge', 'Twilio 技能和 MCP 提供流程化知识'],
        ['Query cloud costs, manage cost reports, budgets, alerts, and recommendations', '查询云成本，管理成本报告、预算、告警和建议'],
        ['Query cloud costs, manage cost reports', '查询云成本，管理成本报告'],
        ['Microsoft Azure MCP and Skills integration for cloud resource management', '用于云资源管理的 Microsoft Azure MCP 与技能集成'],
        ['Microsoft Azure MCP and Skills integration', 'Microsoft Azure MCP 与技能集成'],
        ['Comprehensive skill for the entire Temporal lifecycle', '覆盖整个 Temporal 生命周期的综合技能'],
        ['Configures or troubleshoots the Datadog MCP server', '配置或排查 Datadog MCP 服务器'],
        ['Configures or troubleshoots the Datadog MCP server `plugin-datadog-datadog`.', '配置或排查 Datadog MCP 服务器 `plugin-datadog-datadog`。'],
        ['Use when the user wants to change the Datadog domain, switch organizations', '当用户想更改 Datadog 域名、切换组织时使用'],
        ['First-time initialization of the Datadog MCP server', '首次初始化 Datadog MCP 服务器'],
        ['First-time initialization of the Datadog MCP server `plugin-datadog-datadog`.', '首次初始化 Datadog MCP 服务器 `plugin-datadog-datadog`。'],
        ['When fulfilling requests that involve Datadog, use MCP tools', '处理涉及 Datadog 的请求时，使用 MCP 工具'],
        ['Manages toolsets for the Datadog MCP server', '管理 Datadog MCP 服务器的工具集'],
        ['Manages toolsets for the Datadog MCP server `plugin-datog-datadog`.', '管理 Datadog MCP 服务器 `plugin-datog-datadog` 的工具集。'],
        ['Manages toolsets for the Datadog MCP server `plugin-datadog-datadog`.', '管理 Datadog MCP 服务器 `plugin-datadog-datadog` 的工具集。'],
        ['Use when the user wants to view, enable, or disable toolsets', '当用户想查看、启用或禁用工具集时使用'],
        ['The Terraform MCP Server provides', 'Terraform MCP 服务器提供'],
        ['The Terraform MCP Server provide', 'Terraform MCP 服务器提供'],
        ['Telegram channel for Claude Code', 'Claude Code 的 Telegram 频道'],
        ['Telegram channel for Claude Code...', 'Claude Code 的 Telegram 频道...'],
        ['Telegram channel f', 'Claude Code 的 Telegram 频道'],
        ['Create new skills, improve existing', '创建新技能、改进现有技能'],
        ['Create new skills, improve existing...', '创建新技能、改进现有技能...'],
        ['Create new skills, i', '创建新技能、改进现有技能'],
        ['Security reminder hook that warns', '会发出警告的安全提醒钩子'],
        ['Security reminder hook that warns...', '会发出警告的安全提醒钩子...'],
        ['Security reminder hook that warn', '会发出警告的安全提醒钩子'],
        ['Continuous self-referential AI loops', '连续自引用 AI 循环'],
        ['Continuous self-referential AI loo...', '连续自引用 AI 循环...'],
        ['Continuous self-referential AI loo', '连续自引用 AI 循环'],
        ['Comprehensive PR review agents', '全面的 PR 评审智能体'],
        ['Comprehensive PR review agents ...', '全面的 PR 评审智能体...'],
        ['Comprehensive PR review agents', '全面的 PR 评审智能体'],
        ['Browser automation and end-to-end', '浏览器自动化和端到端'],
        ['Browser automation and end-to-e', '浏览器自动化和端到端'],
        ['Creates interactive HTML playground', '创建交互式 HTML 演示环境'],
        ['Creates interactive HTML playgro', '创建交互式 HTML 演示环境'],
        ['Plugin development toolkit with skills', '带技能的插件开发工具包'],
        ['Plugin development toolkit with s...', '带技能的插件开发工具包...'],
        ['Plugin development toolkit with s', '带技能的插件开发工具包'],
        ['Skills for designing and building MCP', '用于设计和构建 MCP 的技能'],
        ['Generate an explorable HTML repo', '生成可浏览的 HTML 仓库报告'],
        ['server for code intelligence', '代码智能服务器'],
        ['and the most expensive prompts', '以及最昂贵的提示词'],
        ['cache efficiency', '缓存效率'],
        ['subagents', '子智能体'],
        ['session usage', '会话用量']
    ];

    function FanYi_ShiChang_MiaoShu(text) {
        if (!text) return null;
        if (/^[\\s\\w.-]+$/.test(text) && text.length < 60 && text.indexOf(' ') === -1) return null;

        var result = text;
        var changed = false;
        for (var i = 0; i < ShiChang_MiaoShu_SuiPian.length; i++) {
            var pair = ShiChang_MiaoShu_SuiPian[i];
            var neo = result.split(pair[0]).join(pair[1]);
            if (pair[0].indexOf('...') !== -1) {
                neo = neo.split(pair[0].replace(/\.\.\./g, '…')).join(pair[1].replace(/\.\.\./g, '…'));
            }
            if (neo !== result) {
                result = neo;
                changed = true;
            }
        }
        return changed ? result : null;
    }

    function Shi_YiFanYi_De_ShiChang_WenBen(text) {
        return !!(text && /[\u4e00-\u9fff]/.test(text));
    }

    function Shi_ShiChang_YingWen_MiaoShu(text) {
        if (!text) return false;
        var trimmed = GuiYiHua_WenBen(text);
        if (trimmed.length < 18 || trimmed.length > 500) return false;
        if (/[\u4e00-\u9fff]/.test(trimmed)) return false;
        if (!/[A-Za-z]/.test(trimmed) || trimmed.indexOf(' ') === -1) return false;
        if (/^[\w.-]+$/.test(trimmed)) return false;
        if (/^(Search|Get|Add to Cursor|Browse Marketplace|Suggested|Featured|Documentation)$/i.test(trimmed)) return false;
        return true;
    }

    function FanYi_ShiChang_ZaiXian(node, original) {
        if (!Shi_ShiChang_YingWen_MiaoShu(original)) return;
        if (Shi_YiFanYi_De_ShiChang_WenBen(node.textContent || '')) return;
        if (ShiChang_ZaiXianFanYi_BenLun >= 8) return;
        var key = 'cursor_hanhua_market_cache_' + original;
        var cached = null;
        try { cached = localStorage.getItem(key); } catch (e) {}
        if (cached) {
            node.__cursorShiChangYuanWen = original;
            node.__cursorShiChangYiWen = cached;
            node.textContent = cached;
            return;
        }
        if (ShiChang_ZaiXianFanYi_Zhong.has(original)) return;
        ShiChang_ZaiXianFanYi_Zhong.add(original);
        ShiChang_ZaiXianFanYi_BenLun++;

        var url = 'https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=zh-CN&dt=t&q=' + encodeURIComponent(original);
        fetch(url)
            .then(function(resp) { return resp.json(); })
            .then(function(data) {
                var parts = data && data[0] ? data[0] : [];
                var translated = '';
                for (var i = 0; i < parts.length; i++) {
                    if (parts[i] && parts[i][0]) translated += parts[i][0];
                }
                translated = translated.trim();
                if (!translated || translated === original || !/[\u4e00-\u9fff]/.test(translated)) return;
                try { localStorage.setItem(key, translated); } catch (e) {}
                if (ShiChang_FanYi_Kai && node.__cursorShiChangYuanWen === original) {
                    node.__cursorShiChangYiWen = translated;
                    node.textContent = translated;
                }
            })
            .catch(function() {})
            .finally(function() { ShiChang_ZaiXianFanYi_Zhong.delete(original); });
    }

    function TuiDuan_ChaJian_ZhongWen(name) {
        if (!name || name.indexOf(' ') !== -1 || name.indexOf('（') !== -1) return null;
        if (!/[-_]/.test(name)) return null;
        var parts = name.toLowerCase().split(/[-_]+/);
        var out = [];
        for (var i = 0; i < parts.length; i++) {
            var word = ShiChang_MingCheng_CiGen[parts[i]];
            if (word) out.push(word);
        }
        if (out.length < 2) return null;
        var joined = out.join(' ');
        return joined.length > 0 ? joined : null;
    }

    function Shi_ShiChang_Ye() {
        if (!document.body) return false;
        var now = Date.now();
        if (now - ShiChang_Ye_HuanCun.time < 1200) return ShiChang_Ye_HuanCun.value;
        var text = GuiYiHua_WenBen(document.body.textContent || '');
        if (!text) return false;
        var value = (
            text.indexOf('claude-plugins-official') !== -1 ||
            text.indexOf('Search skills, rules, subagents') !== -1 ||
            text.indexOf('Add to Cursor') !== -1 ||
            text.indexOf('All Plugins') !== -1 ||
            text.indexOf('Suggested') !== -1 ||
            text.indexOf('Search or Paste Link') !== -1 ||
            text.indexOf('Browse Marketplace') !== -1 ||
            text.indexOf('Datadog') !== -1 ||
            text.indexOf('生成可浏览的 Claude Code') !== -1 ||
            (text.indexOf('插件') !== -1 && (text.indexOf('推荐') !== -1 || text.indexOf('浏览市场') !== -1 || text.indexOf('暂无插件') !== -1)) ||
            (text.indexOf('市场') !== -1 && (text.indexOf('精选') !== -1 || text.indexOf('全部插件') !== -1 || text.indexOf('添加到 Cursor') !== -1))
        );
        ShiChang_Ye_HuanCun.time = now;
        ShiChang_Ye_HuanCun.value = value;
        return value;
    }

    function BianLi_ShiChang_WenBen(callback) {
        if (!document.body) return;
        var walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
        var node;
        while ((node = walker.nextNode())) {
            if (Shi_BianJiQi_QuYu(node)) continue;
            var parent = node.parentElement;
            if (!parent) continue;
            if (parent.closest('input, textarea, select, [contenteditable="true"]')) continue;
            callback(node);
        }
    }

    function XiuZheng_ShiChang_FanYi() {
        if (!Shi_ShiChang_Ye()) return;
        ShiChang_ZaiXianFanYi_BenLun = 0;
        BianLi_ShiChang_WenBen(function(node) {
            if (ShiChang_FanYi_Kai) {
                if (node.__cursorShiChangYiWen && node.textContent === node.__cursorShiChangYiWen) return;
                var original = node.__cursorShiChangYuanWen || node.textContent;
                if (Shi_YiFanYi_De_ShiChang_WenBen(original)) return;
                var translated = FanYi_ShiChang_MiaoShu(original);
                if (translated && translated !== node.textContent) {
                    node.__cursorShiChangYuanWen = original;
                    node.__cursorShiChangYiWen = translated;
                    node.textContent = translated;
                } else {
                    node.__cursorShiChangYuanWen = original;
                    if (ShiChang_ZaiXianFanYi_Kai) FanYi_ShiChang_ZaiXian(node, original);
                }
            } else if (node.__cursorShiChangYuanWen) {
                node.textContent = node.__cursorShiChangYuanWen;
            }
        });
        XiuZheng_ShiChang_MingCheng();
    }

    function ZhuiJia_ZhongWen_MingCheng(text, map) {
        if (!text || text.indexOf('（') !== -1) return null;
        var key = GuiYiHua_WenBen(text);
        var cn = map[key] || TuiDuan_ChaJian_ZhongWen(key);
        if (!cn) return null;
        return text + '（' + cn + '）';
    }

    function XiuZheng_ShiChang_MingCheng() {
        if (!ShiChang_FanYi_Kai) return;
        var elements = document.querySelectorAll('div, span, p, label, a');
        for (var i = 0; i < elements.length; i++) {
            var el = elements[i];
            if (!el || el.children.length > 0) continue;
            if (el.closest('input, textarea, select, [contenteditable="true"]')) continue;
            var raw = el.textContent || '';
            var trimmed = GuiYiHua_WenBen(raw);
            if (!trimmed || trimmed.length > 80 || trimmed.indexOf('（') !== -1) continue;

            var appended = ZhuiJia_ZhongWen_MingCheng(raw, ShiChang_ChaJian_MingCheng) || ZhuiJia_ZhongWen_MingCheng(raw, ShiChang_JiNeng_MingCheng);
            if (appended) {
                el.__cursorShiChangYuanWen = el.__cursorShiChangYuanWen || raw;
                el.textContent = appended;
                if (el.firstChild && el.firstChild.nodeType === Node.TEXT_NODE) {
                    el.firstChild.__cursorShiChangYuanWen = raw;
                    el.firstChild.__cursorShiChangYiWen = appended;
                }
            }
        }

        BianLi_ShiChang_WenBen(function(node) {
            var text = node.textContent || '';
            var trimmed = GuiYiHua_WenBen(text);
            if (!trimmed || trimmed.length > 80) return;

            var pluginName = ZhuiJia_ZhongWen_MingCheng(text, ShiChang_ChaJian_MingCheng);
            if (pluginName) {
                node.__cursorShiChangYuanWen = node.__cursorShiChangYuanWen || text;
                node.textContent = pluginName;
                return;
            }

            var skillName = ZhuiJia_ZhongWen_MingCheng(text, ShiChang_JiNeng_MingCheng);
            if (skillName) {
                node.__cursorShiChangYuanWen = node.__cursorShiChangYuanWen || text;
                node.textContent = skillName;
            }
        });
    }

    function GengXin_ShiChang_QieHuan_AnNiu() {
        var id = 'cursor-hanhua-market-toggle';
        var old = document.getElementById(id);
        if (!Shi_ShiChang_Ye()) {
            if (old) old.remove();
            return;
        }

        var btn = old;
        if (!btn) {
            btn = document.createElement('button');
            btn.id = id;
            btn.type = 'button';
            btn.style.cssText = 'position:fixed;right:84px;top:48px;z-index:999999;border:1px solid #d0d7de;background:#ffffff;color:#1f2328;border-radius:6px;padding:5px 10px;font-size:12px;line-height:18px;box-shadow:0 4px 16px rgba(31,35,40,.12);cursor:pointer;';
            btn.addEventListener('mouseenter', function() { btn.style.background = '#f6f8fa'; });
            btn.addEventListener('mouseleave', function() { btn.style.background = '#ffffff'; });
            btn.addEventListener('click', function() {
                ShiChang_FanYi_Kai = !ShiChang_FanYi_Kai;
                try { localStorage.setItem(ShiChang_FanYi_Jian, ShiChang_FanYi_Kai ? '1' : '0'); } catch (err) {}
                XiuZheng_ShiChang_FanYi();
                GengXin_ShiChang_QieHuan_AnNiu();
                TiShi_ShiChang_ZhuangTai();
            });
            document.body.appendChild(btn);
        }

        btn.textContent = ShiChang_FanYi_Kai ? '插件描述：中文' : '插件描述：英文';
        btn.title = '切换市场插件描述显示语言';
    }

    function TiShi_ShiChang_ZhuangTai() {
        var old = document.getElementById('cursor-hanhua-market-toast');
        if (old) old.remove();
        var div = document.createElement('div');
        div.id = 'cursor-hanhua-market-toast';
        div.textContent = ShiChang_FanYi_Kai ? '市场插件描述：中文' : '市场插件描述：英文';
        div.style.cssText = 'position:fixed;right:24px;bottom:28px;z-index:999999;background:#1f2937;color:#fff;padding:8px 12px;border-radius:6px;font-size:12px;box-shadow:0 8px 24px rgba(0,0,0,.18);';
        document.body.appendChild(div);
        setTimeout(function() { if (div.parentElement) div.remove(); }, 1600);
    }

    function ZhuCe_ShiChang_KuaiJieJian() {
        if (window.__cursorHanhuaMarketHotkey) return;
        window.__cursorHanhuaMarketHotkey = true;
        document.addEventListener('keydown', function(e) {
            if (e.ctrlKey && e.altKey && !e.shiftKey && String(e.key || '').toLowerCase() === 'm') {
                ShiChang_FanYi_Kai = !ShiChang_FanYi_Kai;
                try { localStorage.setItem(ShiChang_FanYi_Jian, ShiChang_FanYi_Kai ? '1' : '0'); } catch (err) {}
                XiuZheng_ShiChang_FanYi();
                TiShi_ShiChang_ZhuangTai();
            }
        }, true);
    }

    // ================================================================
    // SECTION 3: 用量显示
    // ================================================================

    var YONG_LIANG = ''' + YongLiang_Json + ''';
    var _XHJ_LP = "''' + BianMa_LingPai_Str + '''";

    function _JieMa() { try { return atob(_XHJ_LP); } catch(e) { return null; } }

    function GeShiHua_LingPai(n) {
        if (n >= 1e9) return (n / 1e9).toFixed(1) + 'B';
        if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
        if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
        return n.toString();
    }

    function GengXin_KaPian() {
        var old = document.getElementById('cursor-yongliang-xianshi');
        if (!old) return;
        var par = old.parentElement;
        if (!par) return;
        var neo = ChuangJian_YongLiang_YuanSu();
        if (neo) par.replaceChild(neo, old);
    }

    var _ZhengZaiShuaXin = false;

    function ShiShi_ShuaXin(ShiDianJi) {
        var lp = _JieMa();
        if (!lp) return;
        if (_ZhengZaiShuaXin) return;
        _ZhengZaiShuaXin = true;

        if (ShiDianJi) {
            var card = document.getElementById('cursor-yongliang-xianshi');
            if (card) card.style.opacity = '0.5';
        }

        try {
            var xhr = new XMLHttpRequest();
            xhr.open('GET', 'https://api2.cursor.sh/auth/usage', true);
            xhr.setRequestHeader('Authorization', 'Bearer ' + lp);
            xhr.setRequestHeader('Accept', 'application/json');
            xhr.onload = function() {
                if (xhr.status === 200) {
                    try {
                        var data = JSON.parse(xhr.responseText);
                        if (data['gpt-4']) {
                            YONG_LIANG.gaoJiYong = data['gpt-4'].numRequests || 0;
                            YONG_LIANG.gaoJiXian = data['gpt-4'].maxRequestUsage || 0;
                        }
                        if (data.startOfMonth) {
                            var sm = new Date(data.startOfMonth);
                            if (!isNaN(sm.getTime())) {
                                YONG_LIANG.jiFeiKaiShi = sm.toISOString().substring(0, 10);
                                var em = new Date(sm);
                                em.setMonth(em.getMonth() + 1);
                                YONG_LIANG.jiFeiJieShu = em.toISOString().substring(0, 10);
                            }
                        }
                    } catch(e) { console.log('[HanHua] parse error', e); }
                }
                _ZhengZaiShuaXin = false;
                YONG_LIANG._shiShi = true;
                GengXin_KaPian();
            };
            xhr.onerror = function() { _ZhengZaiShuaXin = false; GengXin_KaPian(); };
            xhr.send();
        } catch(e) { _ZhengZaiShuaXin = false; }
    }

    function _ce(tag, css, txt) {
        var e = document.createElement(tag);
        if (css) e.style.cssText = css;
        if (txt) e.appendChild(document.createTextNode(txt));
        return e;
    }

    function _bar(pct, color, h) {
        var outer = _ce('div', 'width:100%;height:' + (h||4) + 'px;background:rgba(255,255,255,0.08);border-radius:99px;overflow:hidden;');
        var inner = _ce('div', 'width:' + Math.min(pct, 100).toFixed(1) + '%;height:100%;background:' + color + ';border-radius:99px;transition:width 0.5s;');
        outer.appendChild(inner);
        return outer;
    }

    function ChuangJian_YongLiang_YuanSu() {
        if (!YONG_LIANG || !YONG_LIANG.youXiao) return null;

        var zP = YONG_LIANG.zongXian > 0 ? (YONG_LIANG.zongYong / YONG_LIANG.zongXian * 100) : 0;
        var gP = YONG_LIANG.gaoJiXian > 0 ? (YONG_LIANG.gaoJiYong / YONG_LIANG.gaoJiXian * 100) : 0;
        var zC = zP < 60 ? '#4ade80' : (zP < 85 ? '#fbbf24' : '#ef4444');
        var gC = gP < 60 ? '#38bdf8' : (gP < 85 ? '#fbbf24' : '#ef4444');

        var W = _ce('div', 'margin:6px 0 2px 0;cursor:pointer;user-select:none;transition:opacity 0.3s;');
        W.id = 'cursor-yongliang-xianshi';
        W.title = '\\u70b9\\u51fb\\u5237\\u65b0\\u7528\\u91cf\\u6570\\u636e';
        W.addEventListener('click', function(e) { e.stopPropagation(); ShiShi_ShuaXin(true); });

        var r1 = _ce('div', 'margin-bottom:4px;');
        var t1 = _ce('div', 'font-size:11px;color:rgba(228,228,228,0.55);margin-bottom:2px;');
        t1.appendChild(document.createTextNode('\\u603b\\u7528\\u91cf '));
        t1.appendChild(_ce('span', 'color:' + zC + ';font-weight:600;', '' + YONG_LIANG.zongYong));
        t1.appendChild(document.createTextNode(' / ' + YONG_LIANG.zongXian));
        r1.appendChild(t1);
        r1.appendChild(_bar(zP, zC, 3));
        W.appendChild(r1);

        if (YONG_LIANG.gaoJiXian > 0) {
            var r2 = _ce('div', 'margin-bottom:4px;');
            var t2 = _ce('div', 'font-size:11px;color:rgba(228,228,228,0.55);margin-bottom:2px;');
            t2.appendChild(document.createTextNode('\\u9ad8\\u7ea7\\u6a21\\u578b '));
            t2.appendChild(_ce('span', 'color:' + gC + ';font-weight:600;', '' + YONG_LIANG.gaoJiYong));
            t2.appendChild(document.createTextNode(' / ' + YONG_LIANG.gaoJiXian));
            r2.appendChild(t2);
            r2.appendChild(_bar(gP, gC, 3));
            W.appendChild(r2);
        }

        if (YONG_LIANG.jiFeiJieShu) {
            var r3 = _ce('div', 'margin-bottom:2px;');
            var t3 = _ce('div', 'font-size:11px;color:rgba(228,228,228,0.55);');
            t3.appendChild(document.createTextNode('\\u91cd\\u7f6e\\u65e5\\u671f :'));
            t3.appendChild(_ce('span', 'color:#a78bfa;font-weight:600;', YONG_LIANG.jiFeiJieShu));
            r3.appendChild(t3);
            W.appendChild(r3);

            var jinTian = new Date();
            var jinTianStr = jinTian.getFullYear() + '-' + ('0' + (jinTian.getMonth() + 1)).slice(-2) + '-' + ('0' + jinTian.getDate()).slice(-2);
            var chongZhiRi = new Date(YONG_LIANG.jiFeiJieShu + 'T00:00:00');
            var jinTianLing = new Date(jinTianStr + 'T00:00:00');
            var chaTian = Math.ceil((chongZhiRi.getTime() - jinTianLing.getTime()) / 86400000);

            var r4 = _ce('div', 'margin-bottom:2px;');
            var t4 = _ce('div', 'font-size:11px;color:rgba(228,228,228,0.55);');
            t4.appendChild(document.createTextNode('\\u4eca\\u5929\\u65e5\\u671f :'));
            t4.appendChild(_ce('span', 'color:#94a3b8;font-weight:600;', jinTianStr));
            r4.appendChild(t4);
            W.appendChild(r4);

            var r5 = _ce('div', 'margin-bottom:2px;');
            var t5 = _ce('div', 'font-size:11px;color:rgba(228,228,228,0.55);');
            var daoJiShi = chaTian > 0 ? chaTian + ' \\u5929\\u540e\\u91cd\\u7f6e' : (chaTian === 0 ? '\\u4eca\\u5929\\u91cd\\u7f6e' : '\\u5df2\\u8fc7\\u91cd\\u7f6e\\u65e5');
            var daoJiSe = chaTian <= 3 ? '#fbbf24' : '#4ade80';
            t5.appendChild(document.createTextNode('\\u5012\\u8ba1\\u65f6   :'));
            t5.appendChild(_ce('span', 'color:' + daoJiSe + ';font-weight:600;', daoJiShi));
            r5.appendChild(t5);
            W.appendChild(r5);
        }

        return W;
    }

    function YinCang_TouXiang(container) {
        var allEl = container.querySelectorAll('div, span');
        for (var i = 0; i < allEl.length; i++) {
            var el = allEl[i];
            var cs = window.getComputedStyle(el);
            var w = parseInt(cs.width, 10);
            var h = parseInt(cs.height, 10);
            var br = cs.borderRadius;
            if (w >= 20 && w <= 48 && h >= 20 && h <= 48 && w === h && (br === '50%' || br === '9999px' || parseInt(br, 10) >= w / 2)) {
                var txt = (el.textContent || '').trim();
                if (txt.length <= 2) {
                    el.style.display = 'none';
                    console.log('[HanHua] Avatar hidden:', txt, el.tagName, el.className);
                    return;
                }
            }
        }
    }

    function ChaRu_YongLiang_XianShi() {
        if (document.getElementById('cursor-yongliang-xianshi')) return;
        if (!YONG_LIANG || !YONG_LIANG.youXiao) return;

        var YuanSu = ChuangJian_YongLiang_YuanSu();
        if (!YuanSu) return;

        var walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
        var YouXiangJieDian = null;
        var YouXiangRe = /[a-zA-Z0-9._+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}/;
        while (walker.nextNode()) {
            var nd = walker.currentNode;
            var val = (nd.textContent || '').trim();
            if (YouXiangRe.test(val) && val.length < 80) {
                var pEl = nd.parentElement;
                if (pEl && !pEl.closest('.monaco-editor') && !pEl.closest('textarea') && !pEl.closest('input')) {
                    YouXiangJieDian = pEl;
                    console.log('[HanHua] Found email node:', val, pEl.tagName, pEl.className);
                    break;
                }
            }
        }

        if (!YouXiangJieDian) {
            console.log('[HanHua] Email node not found, skipping usage card');
            return;
        }

        var ZhangHuKuai = null;
        var cur = YouXiangJieDian;
        for (var up = 0; up < 8; up++) {
            if (!cur.parentElement || cur.parentElement === document.body) break;
            var p = cur.parentElement;
            var txt = p.textContent || '';
            console.log('[HanHua] depth=' + up, 'tag=' + p.tagName, 'children=' + p.childElementCount, 'txt=' + txt.substring(0, 60));
            if (/Pro|Plan|\\u4e13\\u4e1a|\\u8ba1\\u5212|\\u7ba1\\u7406|Manage/.test(txt) && p.childElementCount >= 2) {
                ZhangHuKuai = p;
                console.log('[HanHua] Account block matched at depth=' + up);
                break;
            }
            cur = p;
        }

        if (ZhangHuKuai) {
            YinCang_TouXiang(ZhangHuKuai);
            ZhangHuKuai.appendChild(YuanSu);
            console.log('[HanHua] Usage card appended inside account block, children now=' + ZhangHuKuai.childElementCount);
            return;
        }

        console.log('[HanHua] Account block not found, using fallback');
        var parent = YouXiangJieDian;
        for (var i = 0; i < 3; i++) {
            if (parent.parentElement && parent.parentElement !== document.body) {
                parent = parent.parentElement;
            }
        }
        parent.appendChild(YuanSu);
        console.log('[HanHua] Usage card appended (fallback) to', parent.tagName, parent.className);
    }

    // ================================================================
    // SECTION 4: 初始化
    // ================================================================

    function ChuShiHua() {
        var target = document.documentElement || document.body;
        if (!target) { setTimeout(ChuShiHua, 50); return; }
        ZhuCe_ShiChang_KuaiJieJian();

        var GuanChaQi = new MutationObserver(GuanCha_HuiDiao);
        GuanChaQi.observe(target, { childList: true, subtree: true });

        setTimeout(function() {
            if (document.body) {
                FanYi_ZiShu(document.body);
                PaiDui_QuanJuXiuZheng();
                if (_XHJ_LP) { setTimeout(function() { ShiShi_ShuaXin(false); }, 1500); }
            }
        }, 500);

        setTimeout(function() {
            if (document.body) {
                FanYi_ZiShu(document.body);
                PaiDui_QuanJuXiuZheng();
            }
        }, 2500);

        if (_XHJ_LP) {
            setInterval(function() {
                if (document.getElementById('cursor-yongliang-xianshi')) {
                    ShiShi_ShuaXin(false);
                }
            }, 60000);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', ChuShiHua);
    } else {
        ChuShiHua();
    }
})();
'''


# ============================================================
# ★★★ 文件路径函数 ★★★
# ============================================================

def HuoQu_GongZuoTai_LuJing():
    """获取 workbench 目录完整路径"""
    return os.path.join(HuoQu_Cursor_App_MuLu(CURSOR_AN_ZHUANG_LU_JING), GONG_ZUO_TAI_HTML_XIANG_DUI)


def HuoQu_Product_LuJing():
    """获取 product.json 完整路径"""
    return os.path.join(HuoQu_Cursor_App_MuLu(CURSOR_AN_ZHUANG_LU_JING), "product.json")


def HuoQu_HTML_LuJing():
    """获取 workbench.html 完整路径"""
    return os.path.join(HuoQu_GongZuoTai_LuJing(), GONG_ZUO_TAI_HTML_MING)


def HuoQu_JS_LuJing():
    """获取翻译 JS 文件完整路径"""
    return os.path.join(HuoQu_GongZuoTai_LuJing(), HAN_HUA_JS_MING)


def HuoQu_BeiFen_LuJing():
    """获取备份文件路径"""
    return HuoQu_HTML_LuJing() + BEI_FEN_HOU_ZHUI


# ============================================================
# ★★★ 注入与恢复函数 ★★★
# ============================================================

def JianCha_YiZhuRu():
    """检查是否已经注入过翻译脚本"""
    LuJing_Html = HuoQu_HTML_LuJing()
    if not os.path.exists(LuJing_Html):
        return False
    with open(LuJing_Html, 'r', encoding='utf-8') as WenJian:
        NeiRong = WenJian.read()
    return ZHU_RU_BIAO_JI in NeiRong


def ChuangJian_BeiFen():
    """创建 workbench.html 的备份"""
    LuJing_Html = HuoQu_HTML_LuJing()
    LuJing_BeiFen = HuoQu_BeiFen_LuJing()
    if not os.path.exists(LuJing_BeiFen):
        shutil.copy2(LuJing_Html, LuJing_BeiFen)
        print(f"[备份] 已创建备份: {LuJing_BeiFen}")
    else:
        print(f"[备份] 备份已存在: {LuJing_BeiFen}")


def XieRu_FanYi_JS(YongLiang_ShuJu, LingPai=""):
    """将翻译 + 用量 JavaScript 文件写入 Cursor 目录"""
    LuJing_Js = HuoQu_JS_LuJing()
    JS_NeiRong = ShengCheng_JS_DaiMa(YongLiang_ShuJu, LingPai)
    with open(LuJing_Js, 'w', encoding='utf-8') as WenJian:
        WenJian.write(JS_NeiRong)
    print(f"[写入] 脚本已写入: {LuJing_Js}")


def ZhuRu_HTML():
    """在 workbench.html 中注入脚本引用"""
    LuJing_Html = HuoQu_HTML_LuJing()
    with open(LuJing_Html, 'r', encoding='utf-8') as WenJian:
        NeiRong = WenJian.read()

    ZhuRu_DaiMa = f'\n\t{ZHU_RU_BIAO_JI}\n\t<script src="./{HAN_HUA_JS_MING}"></script>\n'

    if '</body>' in NeiRong:
        NeiRong = NeiRong.replace('</body>', f'</body>\n{ZhuRu_DaiMa}')
    else:
        NeiRong = NeiRong.replace('</html>', f'{ZhuRu_DaiMa}\n</html>')

    with open(LuJing_Html, 'w', encoding='utf-8') as WenJian:
        WenJian.write(NeiRong)

    print(f"[注入] 已在 workbench.html 中注入脚本引用")
    GengXin_JiaoYan_Zhi()


def GengXin_JiaoYan_Zhi():
    """更新 product.json 中 workbench.html 的校验哈希值"""
    LuJing_Product = HuoQu_Product_LuJing()
    LuJing_Html = HuoQu_HTML_LuJing()

    if not os.path.exists(LuJing_Product):
        print(f"[警告] 未找到 product.json: {LuJing_Product}")
        return

    with open(LuJing_Html, 'rb') as WenJian:
        ShuJu = WenJian.read()
    HaXi_Zhi = base64.b64encode(hashlib.sha256(ShuJu).digest()).decode('utf-8').rstrip('=')

    LuJing_Product_BeiFen = LuJing_Product + BEI_FEN_HOU_ZHUI
    if not os.path.exists(LuJing_Product_BeiFen):
        shutil.copy2(LuJing_Product, LuJing_Product_BeiFen)

    with open(LuJing_Product, 'r', encoding='utf-8') as WenJian:
        YuanShi_WenBen = WenJian.read()

    import re
    JiaoYan_Jian = "vs/code/electron-sandbox/workbench/workbench.html"
    MoShi = re.compile(r'("' + re.escape(JiaoYan_Jian) + r'"\s*:\s*")([^"]*?)(")')
    PiPei = MoShi.search(YuanShi_WenBen)
    if PiPei:
        XinWenBen = YuanShi_WenBen[:PiPei.start(2)] + HaXi_Zhi + YuanShi_WenBen[PiPei.end(2):]
        with open(LuJing_Product, 'w', encoding='utf-8') as WenJian:
            WenJian.write(XinWenBen)
        print(f"[校验] 已更新 product.json 中的校验值")
    else:
        print(f"[警告] product.json 中未找到 workbench.html 的校验条目")


def HuoQu_YuYan_Bao_PeiZhi_LuJing():
    """获取 Cursor 用户数据目录中的 languagepacks.json 路径"""
    return os.path.join(CURSOR_SHU_JU_LU_JING, "languagepacks.json")


def DuQu_YuYan_Bao_PeiZhi():
    """读取 languagepacks.json"""
    LuJing = HuoQu_YuYan_Bao_PeiZhi_LuJing()
    if not os.path.exists(LuJing):
        print(f"[语言包] 未找到 languagepacks.json: {LuJing}")
        return None, LuJing

    try:
        with open(LuJing, 'r', encoding='utf-8') as WenJian:
            return json.load(WenJian), LuJing
    except Exception as CuoWu:
        print(f"[语言包] 读取 languagepacks.json 失败: {CuoWu}")
        return None, LuJing


def HuoQu_JianTiZhongWen_PeiZhi(XinXi):
    """从 languagepacks.json 中查找 zh-cn 配置"""
    if not XinXi:
        return None, None

    for Jian in ("zh-cn", "zh-CN"):
        if Jian in XinXi:
            return Jian, XinXi[Jian]

    print("[语言包] 未找到 zh-cn 语言包配置，跳过 Cursor 私有扩展翻译桥接")
    return None, None


def XieRu_KuoZhan_FanYi_QiaoJie():
    """把 Cursor 私有扩展翻译接到现有 zh-cn 语言包通道"""
    XinXi, LuJing = DuQu_YuYan_Bao_PeiZhi()
    Jian, PeiZhi = HuoQu_JianTiZhongWen_PeiZhi(XinXi)
    if not Jian or not PeiZhi:
        return

    FanYiLieBiao = PeiZhi.setdefault("translations", {})
    ZhuFanYi = FanYiLieBiao.get("vscode")
    if not ZhuFanYi:
        print("[语言包] zh-cn 配置缺少 vscode 主翻译路径，跳过私有扩展翻译桥接")
        return

    KuoZhanMuLu = os.path.dirname(ZhuFanYi)
    os.makedirs(KuoZhanMuLu, exist_ok=True)

    ShiFouGengXin = False
    for KuoZhanId, FanYiNeiRong in KUO_ZHAN_FAN_YI_QIAO_JIE.items():
        WenJianMing = KuoZhanId.replace('/', '.').replace('\\', '.') + ".i18n.json"
        WenJianLuJing = os.path.join(KuoZhanMuLu, WenJianMing)
        BiaoZhunNeiRong = {
            "": [
                "Generated by CursorHanHua_GongJu.py for Cursor private extensions."
            ],
            "version": "1.0.0",
            "contents": FanYiNeiRong
        }

        YuanYou = None
        if os.path.exists(WenJianLuJing):
            try:
                with open(WenJianLuJing, 'r', encoding='utf-8') as WenJian:
                    YuanYou = json.load(WenJian)
            except Exception:
                YuanYou = None

        if YuanYou != BiaoZhunNeiRong:
            with open(WenJianLuJing, 'w', encoding='utf-8') as WenJian:
                json.dump(BiaoZhunNeiRong, WenJian, ensure_ascii=False, indent=2)
                WenJian.write('\n')
            print(f"[语言包] 已写入私有扩展翻译: {WenJianLuJing}")
            ShiFouGengXin = True

        if FanYiLieBiao.get(KuoZhanId) != WenJianLuJing:
            FanYiLieBiao[KuoZhanId] = WenJianLuJing
            ShiFouGengXin = True

    if ShiFouGengXin:
        with open(LuJing, 'w', encoding='utf-8') as WenJian:
            json.dump(XinXi, WenJian, ensure_ascii=False, indent=2)
            WenJian.write('\n')
        print("[语言包] 已更新 languagepacks.json，重启 Cursor 后私有扩展简中生效")
    else:
        print("[语言包] Cursor 私有扩展翻译桥接已是最新状态")


def YiChu_KuoZhan_FanYi_QiaoJie():
    """移除脚本添加的 Cursor 私有扩展翻译桥接"""
    XinXi, LuJing = DuQu_YuYan_Bao_PeiZhi()
    Jian, PeiZhi = HuoQu_JianTiZhongWen_PeiZhi(XinXi)
    if not Jian or not PeiZhi:
        return

    FanYiLieBiao = PeiZhi.get("translations", {})
    ShiFouGengXin = False

    for KuoZhanId in KUO_ZHAN_FAN_YI_QIAO_JIE:
        WenJianLuJing = FanYiLieBiao.get(KuoZhanId)
        if WenJianLuJing and os.path.exists(WenJianLuJing):
            os.remove(WenJianLuJing)
            print(f"[语言包] 已删除私有扩展翻译: {WenJianLuJing}")
        if KuoZhanId in FanYiLieBiao:
            del FanYiLieBiao[KuoZhanId]
            ShiFouGengXin = True

    if ShiFouGengXin:
        with open(LuJing, 'w', encoding='utf-8') as WenJian:
            json.dump(XinXi, WenJian, ensure_ascii=False, indent=2)
            WenJian.write('\n')
        print("[语言包] 已从 languagepacks.json 移除私有扩展翻译桥接")


def HuiFu_JiaoYan_Zhi():
    """恢复 product.json 的原始校验值"""
    LuJing_Product = HuoQu_Product_LuJing()
    LuJing_Product_BeiFen = LuJing_Product + BEI_FEN_HOU_ZHUI
    if os.path.exists(LuJing_Product_BeiFen):
        shutil.copy2(LuJing_Product_BeiFen, LuJing_Product)
        os.remove(LuJing_Product_BeiFen)
        print(f"[校验] 已恢复 product.json 原始校验值")


def HuiFu_YuanShi():
    """恢复原始的 workbench.html"""
    LuJing_Html = HuoQu_HTML_LuJing()
    LuJing_BeiFen = HuoQu_BeiFen_LuJing()
    LuJing_Js = HuoQu_JS_LuJing()

    if os.path.exists(LuJing_BeiFen):
        shutil.copy2(LuJing_BeiFen, LuJing_Html)
        os.remove(LuJing_BeiFen)
        print(f"[恢复] 已从备份恢复: {LuJing_Html}")
    else:
        print("[恢复] 未找到备份文件，尝试手动移除注入...")
        with open(LuJing_Html, 'r', encoding='utf-8') as WenJian:
            HangLieBiao = WenJian.readlines()
        XinHang = []
        TiaoGuo = False
        for Hang in HangLieBiao:
            if ZHU_RU_BIAO_JI in Hang:
                TiaoGuo = True
                continue
            if TiaoGuo and '<script src="./' + HAN_HUA_JS_MING + '">' in Hang:
                TiaoGuo = False
                continue
            if not TiaoGuo:
                XinHang.append(Hang)
        with open(LuJing_Html, 'w', encoding='utf-8') as WenJian:
            WenJian.writelines(XinHang)
        print(f"[恢复] 已手动移除注入内容")

    HuiFu_JiaoYan_Zhi()

    if os.path.exists(LuJing_Js):
        os.remove(LuJing_Js)
        print(f"[清理] 已删除脚本: {LuJing_Js}")

    YiChu_KuoZhan_FanYi_QiaoJie()

    print("[完成] 已恢复原始状态")


# ============================================================
# ★★★ 主程序 ★★★
# ============================================================

def ZhuChengXu():
    """主程序入口"""
    print("=" * 60)
    print("  Cursor 汉化 + 用量监控工具")
    print(f"  时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 恢复模式
    if len(sys.argv) > 1 and sys.argv[1] == '--huifu':
        print("\n[模式] 恢复原始文件...")
        HuiFu_YuanShi()
        return

    # 检查 Cursor 安装目录
    LuJing_Html = HuoQu_HTML_LuJing()
    if not os.path.exists(LuJing_Html):
        print(f"\n[错误] 未找到 workbench.html: {LuJing_Html}")
        print(f"[提示] 请检查 CURSOR_AN_ZHUANG_LU_JING 是否正确: {CURSOR_AN_ZHUANG_LU_JING}")
        sys.exit(1)

    # 读取认证令牌
    print("\n[步骤 1/5] 读取认证信息...")
    LingPai, YouXiang = DuQu_FangWen_LingPai()
    if LingPai:
        print(f"[认证] 已找到令牌，邮箱: {YouXiang or '未知'}")
    else:
        print("[认证] 未找到认证令牌，将跳过用量获取（仅汉化）")

    # 获取用量数据
    YongLiang_ShuJu = None
    if LingPai:
        print("\n[步骤 2/5] 获取用量数据...")
        YongLiang_ShuJu = ZhengHe_YongLiang_ShuJu(LingPai)
        if YongLiang_ShuJu and YongLiang_ShuJu.get("youXiao"):
            print(f"[用量] 总用量: {YongLiang_ShuJu['zongYong']} / {YongLiang_ShuJu['zongXian']} 次")
            print(f"[用量] 高级请求: {YongLiang_ShuJu['gaoJiYong']} / {YongLiang_ShuJu['gaoJiXian']} 次")
            print(f"[用量] 剩余: {YongLiang_ShuJu['shengYu']} 次")
            if YongLiang_ShuJu.get('jiFeiKaiShi'):
                print(f"[用量] 计费周期: {YongLiang_ShuJu['jiFeiKaiShi']} 至 {YongLiang_ShuJu['jiFeiJieShu']}")
        else:
            print("[用量] 获取用量数据失败，将仅汉化")
    else:
        print("\n[步骤 2/5] 跳过用量获取（无令牌）")

    if not YongLiang_ShuJu:
        YongLiang_ShuJu = {
            "zongYong": 0, "zongXian": 0, "shengYu": 0,
            "gaoJiYong": 0, "gaoJiXian": 0,
            "zongBaiFen": 0, "apiBaiFen": 0,
            "jiFeiKaiShi": "", "jiFeiJieShu": "",
            "gengXinShiJian": "", "jiHua": "", "youXiao": False
        }

    print("\n[步骤 3/5] 更新 Cursor 私有扩展翻译桥接...")
    XieRu_KuoZhan_FanYi_QiaoJie()

    # 检查是否已注入
    if JianCha_YiZhuRu():
        print("\n[检测] 脚本已注入，正在更新...")
        XieRu_FanYi_JS(YongLiang_ShuJu, LingPai or "")
        GengXin_JiaoYan_Zhi()
        print("\n[完成] 脚本已更新！重启 Cursor 生效。")
        return

    # 首次注入
    print(f"\n[步骤 4/5] 创建备份并写入脚本...")
    ChuangJian_BeiFen()
    XieRu_FanYi_JS(YongLiang_ShuJu, LingPai or "")

    print("[步骤 5/5] 注入 HTML 引用...")
    ZhuRu_HTML()

    print("\n" + "=" * 60)
    print("  [完成] Cursor 汉化 + 用量监控 注入成功！")
    print("  请重启 Cursor 以查看效果。")
    print("  如需恢复: python CursorHanHua_GongJu.py --huifu")
    print("  如需更新用量: 重新运行本脚本即可")
    print("=" * 60)


if __name__ == '__main__':
    ZhuChengXu()
