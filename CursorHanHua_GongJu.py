# -*- coding: utf-8 -*-
"""
Cursor 汉化 + 用量监控工具

基于原项目 bjrzs/Cursor_chinese（作者：@bjrzs / 行云流水）二次开发。
原仓库：https://github.com/bjrzs/Cursor_chinese
本仓库：https://github.com/xyiqq/Cursor_chinese

功能：
  1. 将翻译脚本注入 Cursor 的 workbench.html，实现设置页面中文化
  2. 自动从本地数据库读取认证令牌，调用 API 获取用量数据
  3. 在 Cursor 设置页面用户信息区域下方显示实时用量情况

用法：
  python CursorHanHua_GongJu.py              汉化 + 用量显示
  python CursorHanHua_GongJu.py --qi-dong    后台静默检查后启动 Cursor（无窗口）
  python CursorHanHua_GongJu.py --xiu-fu     仅后台静默自愈（不启动）
  python CursorHanHua_GongJu.py --an-zhuang  安装「启动时检查」桌面快捷方式
  python CursorHanHua_GongJu.py --xie-zai    卸载启动快捷方式与旧计划任务
  python CursorHanHua_GongJu.py --huifu      恢复原始文件
"""

import os  # 文件路径操作
import sys  # 系统参数
import shutil  # 文件复制
import datetime  # 时间戳
import hashlib  # 哈希计算
import base64  # Base64 编码
import json  # JSON 读写
import sqlite3  # SQLite 数据库
import subprocess  # 计划任务 / 快捷方式
import urllib.request  # HTTP 请求
import urllib.error  # HTTP 错误处理
import time  # 后台用量轮询

# 本工具版本（与 README 保持一致）
GONG_JU_BAN_BEN = "1.2.1"

# ============================================================
# ★★★ 用户配置区域 ★★★
# ============================================================

# Cursor 安装根目录（留空则自动检测 Windows 常见安装路径）
CURSOR_AN_ZHUANG_LU_JING = ""

# Cursor 用户数据目录（留空则自动检测，或使用 --user-data-dir 自定义目录时手动填写）
CURSOR_SHU_JU_LU_JING = ""

# 以下路径一般不需要修改
GONG_ZUO_TAI_HTML_XIANG_DUI = r"resources\app\out\vs\code\electron-sandbox\workbench"  # workbench 目录相对路径
GONG_ZUO_TAI_HTML_MING = "workbench.html"  # workbench HTML 文件名
HAN_HUA_JS_MING = "cursor_hanhua.js"  # 翻译脚本文件名
YONG_LIANG_LIVE_JSON = "usage_live.json"  # 同目录实时用量（供 JS 同源读取，绕过跨域）
ZHU_RU_BIAO_JI = "<!-- CURSOR_HANHUA_INJECTION -->"  # 注入标记
BEI_FEN_HOU_ZHUI = ".bak"  # 备份文件后缀
ZHUANG_TAI_MU_LU_MING = "Cursor_chinese_hanhua"  # 本工具状态目录名（位于 APPDATA）
ZHUANG_TAI_WEN_JIAN_MING = "injected_state.json"  # 记录已注入的 Cursor 版本
JI_HUA_REN_WU_MING = "CursorChineseAutoHeal"  # 旧版计划任务名（卸载时清理）
ZHUO_MIAN_KUAI_JIE_MING = "Cursor中文.lnk"  # 桌面快捷方式名
QI_DONG_VBS_MING = "QiDong_Cursor_ZhongWen.vbs"  # 无窗口启动器

# API 端点
API_YONG_LIANG = "https://api2.cursor.sh/auth/usage"  # 高级请求用量
API_YONG_LIANG_ZONG_JIE = "https://www.cursor.com/api/usage-summary"  # 总用量摘要
API_GE_REN_XIN_XI = "https://api2.cursor.sh/auth/full_stripe_profile"  # 个人信息

# state.vscdb 中的认证键名
DB_XIANG_DUI_LU_JING = r"User\globalStorage\state.vscdb"  # 数据库相对路径
LING_PAI_JIAN_MING = "cursorAuth/accessToken"  # 访问令牌键名
YOU_XIANG_JIAN_MING = "cursorAuth/cachedEmail"  # 邮箱键名


def _ZiDong_JianCe_AnZhuang_LuJing():
    """自动检测 Cursor 安装目录（Windows 常见路径）"""
    HouXuan = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "cursor"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Cursor"),
        r"C:\Program Files\cursor",
        r"C:\Program Files\Cursor",
        r"D:\Tools\cursor",
    ]
    for LuJing in HouXuan:
        if not LuJing:
            continue
        Html_LuJing = os.path.join(LuJing, GONG_ZUO_TAI_HTML_XIANG_DUI, GONG_ZUO_TAI_HTML_MING)
        if os.path.exists(Html_LuJing):
            return LuJing
    return HouXuan[0] if HouXuan[0] else r"D:\Tools\cursor"


def _ZiDong_JianCe_ShuJu_LuJing():
    """自动检测 Cursor 用户数据目录"""
    HouXuan = [
        os.path.join(os.environ.get("APPDATA", ""), "Cursor"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "cursor", "user"),
        r"D:\Tools\cursor\user",
    ]
    for LuJing in HouXuan:
        Db_LuJing = os.path.join(LuJing, DB_XIANG_DUI_LU_JING)
        if os.path.exists(Db_LuJing):
            return LuJing
    return HouXuan[0] if HouXuan[0] else r"D:\Tools\cursor\user"


def HuoQu_AnZhuang_LuJing():
    """获取最终使用的 Cursor 安装路径"""
    return CURSOR_AN_ZHUANG_LU_JING or _ZiDong_JianCe_AnZhuang_LuJing()


def HuoQu_ShuJu_LuJing():
    """获取最终使用的 Cursor 用户数据路径"""
    return CURSOR_SHU_JU_LU_JING or _ZiDong_JianCe_ShuJu_LuJing()


# ============================================================
# ★★★ 认证与 API 函数 ★★★
# ============================================================

def DuQu_FangWen_LingPai():
    """从 Cursor 本地 state.vscdb 数据库读取访问令牌和用户邮箱"""
    ShuJuKu_LuJing = os.path.join(HuoQu_ShuJu_LuJing(), DB_XIANG_DUI_LU_JING)  # 数据库完整路径
    if not os.path.exists(ShuJuKu_LuJing):  # 检查数据库是否存在
        print(f"[警告] 未找到 Cursor 数据库: {ShuJuKu_LuJing}")
        return None, None

    try:
        LianJie = sqlite3.connect(ShuJuKu_LuJing, timeout=5)  # 连接数据库（允许短暂等待锁）
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

    for ChangShi in range(3):
        try:
            QingQiu = urllib.request.Request(API_YONG_LIANG_ZONG_JIE)  # 创建请求
            QingQiu.add_header('Cookie', f'WorkosCursorSessionToken={Cookie_Zhi}')  # 添加认证 Cookie
            QingQiu.add_header('Accept', 'application/json')  # 期望 JSON 响应
            XiangYing = urllib.request.urlopen(QingQiu, timeout=15)  # 发送请求
            return json.loads(XiangYing.read().decode('utf-8'))  # 解析 JSON 响应
        except Exception as CuoWu:
            if ChangShi < 2:
                time.sleep(1.5)
                continue
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
        "zongBaiFen": 0,     # 总使用百分比（与官网一致，权威字段）
        "shengYuBaiFen": 100,  # 剩余百分比（100 - 总占比）
        "apiBaiFen": 0,      # API 使用百分比
        "autoBaiFen": 0,     # Auto 模型使用百分比
        "jiFeiKaiShi": "",   # 计费周期开始
        "jiFeiJieShu": "",   # 计费周期结束
        "gengXinShiJian": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # 数据更新时间
        "jiHua": "pro",      # 计划类型
        "youXiao": False,    # 数据是否有效（仅 usage-summary 成功时为 True）
        "summaryOk": False,  # usage-summary 是否成功（防止部分 API 失败误标有效）
        "moXingXiangQing": {}  # 各模型详细用量
    }

    # 获取总用量摘要（百分比以该接口为准）
    ZongJie = HuoQu_YongLiang_ZongJie(LingPai)  # 调用 API
    if ZongJie and 'individualUsage' in ZongJie:  # 有有效数据
        JiHua = ZongJie['individualUsage'].get('plan', {})  # 提取计划用量
        ShuJu["zongYong"] = JiHua.get('used', 0)  # 已使用次数
        ShuJu["zongXian"] = JiHua.get('limit', 2000)  # 总限额
        ShuJu["shengYu"] = JiHua.get('remaining', 0)  # 剩余次数
        ShuJu["zongBaiFen"] = round(JiHua.get('totalPercentUsed', 0), 1)  # 总百分比（官网显示值）
        ShuJu["shengYuBaiFen"] = round(max(0, 100 - ShuJu["zongBaiFen"]), 1)  # 剩余百分比
        ShuJu["apiBaiFen"] = round(JiHua.get('apiPercentUsed', 0), 1)  # API 百分比
        ShuJu["autoBaiFen"] = round(JiHua.get('autoPercentUsed', 0), 1)  # Auto 百分比
        ShuJu["jiHua"] = ZongJie.get('membershipType', 'pro')  # 计划类型
        ShuJu["summaryOk"] = True
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
            ShuJu["gaoJiXian"] = GaoJi['gpt-4'].get('maxRequestUsage') or 0

        # gpt-4 限额为空时，不显示高级模型条（官网新版 API 常返回 null）

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

    return ShuJu  # 返回整合后的数据


def DuQu_YongLiang_LiveJson():
    """读取已写入的实时用量 JSON"""
    LuJing = HuoQu_Live_JSON_LuJing()
    if not os.path.exists(LuJing):
        return None
    try:
        with open(LuJing, 'r', encoding='utf-8') as WenJian:
            return json.load(WenJian)
    except Exception:
        return None


def YongLiang_ShuJu_KeXin(ShuJu):
    """仅当 usage-summary 成功时才视为可信用量"""
    return bool(ShuJu and ShuJu.get("summaryOk") and ShuJu.get("youXiao"))


def BuYing_Gai_FuGai_LiveJson(Xin, Jiu):
    """避免用失败/空数据覆盖上次有效用量"""
    if not YongLiang_ShuJu_KeXin(Xin):
        return True
    if not Jiu or not YongLiang_ShuJu_KeXin(Jiu):
        return False
    XinQuanBuWeiLing = (
        (Xin.get("zongBaiFen") or 0) == 0
        and (Xin.get("apiBaiFen") or 0) == 0
        and (Xin.get("autoBaiFen") or 0) == 0
    )
    JiuYouZhi = (
        (Jiu.get("zongBaiFen") or 0) > 0
        or (Jiu.get("apiBaiFen") or 0) > 0
        or (Jiu.get("autoBaiFen") or 0) > 0
    )
    return XinQuanBuWeiLing and JiuYouZhi


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
        ["Tools & MCPs", "工具与 MCP"],
        ["Workspaces", "工作区"],
        ["Worktrees", "工作树"],
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
        ["Tips", "提示"],
        ["Show rotating tips on the empty screen", "在空白屏幕上显示轮播提示"],
        ["Auto-Approve Mode Transitions", "自动批准模式切换"],
        ["Allow Agent to switch model without asking first, such as Agent to Plan or Agent to Debug. When off, Cursor asks before switching.", "允许 Agent 在不询问的情况下切换模型，例如从 Agent 切换到计划或调试模式。关闭时，Cursor 会在切换前询问。"],
        ["Open Agents Window on startup", "启动时打开智能体窗口"],
        ["When launching Cursor, open Agents Window by default", "启动 Cursor 时默认打开智能体窗口"],
        ["Explore subagent model", "探索子智能体模型"],
        ["The Explore subagent is used to do initial research for the main agent", "探索子智能体用于为主智能体进行初步研究"],
        ["Web search tool", "网络搜索工具"],
        ["Web fetch tool", "网络获取工具"],
        ["Enabled by Run everything Auto-Run Mode. Agent bypasses approval prompts for tools including Web Search.", "由[运行所有]自动运行模式启用。Agent 将跳过包括网络搜索在内的工具审批提示。"],
        ["Approvals & Execution for commands, MCP and more", "命令、MCP 等的审批与执行"],
        ["Run Mode", "运行模式"],
        ["Choose how Agents run tools like command execution, MCP, and file writes. All commands will run without approval, classification or sandboxing.", "选择智能体如何运行命令执行、MCP 和文件写入等工具。所有命令将在无需审批、分类或沙盒的情况下运行。"],
        ["Choose how Agents run tools like command execution, MCP, and file writes.", "选择智能体如何运行命令执行、MCP 和文件写入等工具。"],
        ["Usage Chart", "用量图表"],
        ["Control when the usage chart appears at the top of the chat pane", "控制在聊天面板顶部显示用量图表的时机"],
        ["Cursor periodically removes old worktrees to free disk space. Tune how aggressively cleanup runs.", "Cursor 会定期删除旧工作树以释放磁盘空间。可调整清理的积极程度。"],
        ["Max worktrees", "最大工作树数"],
        ["Max total size (GB)", "最大总大小 (GB)"],
        ["Cursor-managed worktrees", "Cursor 管理的工作树"],
        ["No Cursor-managed worktrees on this machine.", "本机上暂无 Cursor 管理的工作树。"],
        ["Retain at most this many Cursor-managed worktrees on disk.", "在磁盘上最多保留此数量的 Cursor 管理工作树。"],
        ["Stop creating new worktrees when total size exceeds this limit.", "当总大小超过此限制时停止创建新工作树。"],

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
        ["Delete Skill", "删除技能"],
        ["Subagents", "子智能体"],
        ["Create specialized agents for complex tasks. Subagents can be invoked by the agent to handle focused work in parallel.", "为复杂任务创建专门的智能体。子智能体可以被智能体调用，以并行处理专注的工作。"],
        ["Create specialized agents to handle focused tasks", "创建专门的智能体来处理专注的任务"],
        ["No Subagents Yet", "暂无子智能体"],
        ["Delete Subagent", "删除子智能体"],
        ["Commands", "命令"],
        ["Create commands to build reusable workflows", "创建命令以构建可复用的工作流"],
        ["Create reusable workflows triggered with / prefix in chat. Use commands to standardize processes and make common tasks more efficient.", "创建在聊天中使用 / 前缀触发的可复用工作流。使用命令来标准化流程，使常见任务更高效。"],
        ["No Commands Yet", "暂无命令"],
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
        ["Add a custom MCP tool in your user MCP config.", "在用户 MCP 配置中添加自定义 MCP 工具。"],
        ["Add Custom MCP", "添加自定义 MCP"],
        ["Configure Team MCP Servers", "配置团队 MCP 服务器"],

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

        // ==================== 索引与文档 (Indexing & Docs) 页面 ====================
        ["Codebase", "代码库"],
        ["Codebase Indexing", "代码库索引"],
        ["Codebase indexing", "代码库索引"],
        ["Learn about codebase indexing", "了解代码库索引"],
        ["Codebase Index deleted", "代码库索引已删除"],
        ["Delete Codebase Index?", "删除代码库索引？"],
        ["Delete Index", "删除索引"],
        ["Index New Folders", "索引新文件夹"],
        ["Index Repositories for Instant Grep", "索引仓库以实现即时搜索"],
        ["Automatically index repositories to speed up Grep searches. All data is stored locally.", "自动索引仓库以加速 Grep 搜索。所有数据都存储在本地。"],
        ["Embed codebase for improved contextual understanding and knowledge.", "嵌入代码库以提高上下文理解和知识。"],
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
        ["Allow Agent to fetch content from URLs", "允许 Agent 从 URL 获取内容"],
        ["Crawl and index custom resources and developer docs", "爬取和索引自定义资源和开发者文档"],
        ["Add Doc", "添加文档"],
        ["Add documentation to use as context. You can also use @Add in Chat or while editing to add a doc.", "添加文档用作上下文。您还可以在聊天中或编辑时使用 @Add 来添加文档。"],
        ["No Docs Added", "暂无已添加的文档"],
        ["Indexing", "索引"],
        ["Automatically index any new folders with fewer than 50,000 files", "自动索引文件数少于 50,000 的新文件夹"],

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
        ["Add or search model", "添加或搜索模型"],
        ["Enter model name", "输入模型名称"],
        ["Enter your OpenAI API Key", "输入您的 OpenAI API 密钥"],
        ["Enter your Anthropic API Key", "输入您的 Anthropic API 密钥"],
        ["Enter your Google AI Studio API Key", "输入您的 Google AI Studio API 密钥"],
        ["Enter your Azure OpenAI API Key", "输入您的 Azure OpenAI API 密钥"],
        ["Turn Off Anthropic Key", "关闭 Anthropic 密钥"],
        ["Turn Off Google Key", "关闭 Google 密钥"],
        ["Select Custom Chime Sound", "选择自定义提示音"],
        ["Legacy Terminal Tool", "旧版终端工具"],
        ["Use the legacy terminal tool in agent mode, for use on systems with unsupported shell configurations", "在智能体模式下使用旧版终端工具，适用于不支持的 Shell 配置系统"],
        ["Use a preview box instead of streaming responses directly into the shell", "使用预览框而不是将响应直接流式传输到 Shell 中"],
        ["Collapse Auto-Run Commands", "折叠自动运行命令"],
        ["Collapse auto-run command output by default in Terminal command previews", "在终端命令预览中默认折叠自动运行命令输出"],

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
        ["User", "用户"],
        ["Agent", "智能体"],
        ["10", "10"],
        ["All Files", "所有文件"],
        ["Audio Files", "音频文件"],
        ["Breadcrumb", "面包屑"],
        ["Island", "浮动岛"],
        ["Start Free Trial", "开始免费试用"],
        ["Start free trial", "开始免费试用"],

        // ==================== 仓库选择器 (Repos) ====================
        ["Repos", "仓库"],
        ["Recents", "最近"],
        ["On This PC", "本机"],
        ["On this PC", "本机"],
        ["On This Mac", "本机"],
        ["On This Computer", "本机"],
        ["This PC", "本机"],
        ["This Mac", "本机"],
        ["This Computer", "本机"],
        ["Cloud", "云端"],
        ["Start from scratch", "从零开始"],
        ["Start From Scratch", "从零开始"],
        ["+ Start from scratch", "从零开始"],
        ["Use Existing...", "使用已有..."],
        ["Use Existing…", "使用已有..."],
        ["Use existing...", "使用已有..."],
        ["Use Existing", "使用已有"],
        ["New Folder", "新建文件夹"],
        ["Add Workspace", "添加工作区"],
        ["Clone Repository", "克隆仓库"],
        ["Connect via SSH", "通过 SSH 连接"],
        ["Connect via WSL", "通过 WSL 连接"],
        ["Connect SSH", "连接 SSH"],
        ["Connect WSL", "连接 WSL"],
        ["Connect", "连接"],
        ["Set Up Workspace", "设置工作区"],
        ["Select a project", "选择项目"],
        ["Select a repository", "选择仓库"],
        ["Select a workspace", "选择工作区"],
        ["Search folders, repos...", "搜索文件夹、仓库..."],
        ["Search folders, repos…", "搜索文件夹、仓库..."],
        ["Search repositories, environments...", "搜索仓库、环境..."],
        ["Search workspaces...", "搜索工作区..."],
        ["Search folders…", "搜索文件夹..."],
        ["New Local Git Repo", "新建本地 Git 仓库"],
        ["Repository URL (https or SSH)", "仓库地址（https 或 SSH）"],

        // ==================== 菜单栏 (Menu Bar) ====================
        ["File", "文件"],
        ["New Agent", "新建智能体"],
        ["New File", "新建文件"],
        ["Open Folder", "打开文件夹"],
        ["Open File...", "打开文件..."],
        ["Open Recent", "打开最近"],
        ["Add Folder to Workspace", "将文件夹添加到工作区"],
        ["Save Workspace As...", "将工作区另存为..."],
        ["Duplicate Workspace", "复制工作区"],
        ["Close Folder", "关闭文件夹"],
        ["Close Workspace", "关闭工作区"],
        ["New Terminal", "新建终端"],
        ["New Browser", "新建浏览器"],
        ["Open Editor Window", "打开编辑器窗口"],
        ["New Window", "新建窗口"],
        ["Close Window", "关闭窗口"],
        ["Close Editor", "关闭编辑器"],
        ["Save", "保存"],
        ["Save As", "另存为"],
        ["Save All", "全部保存"],
        ["Revert File", "还原文件"],
        ["Exit", "退出"],
        ["Edit", "编辑"],
        ["Selection", "选择"],
        ["View", "视图"],
        ["Go", "转到"],
        ["Run", "运行"],
        ["Terminal", "终端"],
        ["Window", "窗口"],
        ["Help", "帮助"],
        ["Undo", "撤销"],
        ["Redo", "重做"],
        ["Cut", "剪切"],
        ["Copy", "复制"],
        ["Paste", "粘贴"],
        ["Select All", "全选"],
        ["Find", "查找"],
        ["Replace", "替换"],
        ["Find in Selection", "在选定内容中查找"],
        ["Find in Files", "在文件中查找"],
        ["Replace in Files", "在文件中替换"],
        ["Format Document", "格式化文档"],
        ["Format Selection", "格式化选定内容"],
        ["Format Document With...", "使用...格式化文档"],
        ["Toggle Line Comment", "切换行注释"],
        ["Toggle Block Comment", "切换块注释"],
        ["Emmet: Expand Abbreviation", "Emmet：展开缩写"],
        ["Go to Definition", "转到定义"],
        ["Go to References", "转到引用"],
        ["Peek Definition", "速览定义"],
        ["Rename Symbol", "重命名符号"],
        ["Change All Occurrences", "更改所有匹配项"],
        ["Refactor...", "重构..."],
        ["Source Action...", "源代码操作..."],
        ["Open Changes", "打开更改"],
        ["Open Browser", "打开浏览器"],
        ["Open File", "打开文件"],
        ["Open Terminal", "打开终端"],
        ["Command Palette...", "命令面板..."],
        ["Quick Open...", "快速打开..."],
        ["Show All Commands", "显示所有命令"],
        ["Go to File...", "转到文件..."],
        ["Go to Symbol in Workspace...", "转到工作区中的符号..."],
        ["Go to Line/Column...", "转到行/列..."],
        ["Go Back", "后退"],
        ["Go Forward", "前进"],
        ["Explorer", "资源管理器"],
        ["Search", "搜索"],
        ["Source Control", "源代码管理"],
        ["Run and Debug", "运行和调试"],
        ["Extensions", "扩展"],
        ["Problems", "问题"],
        ["Output", "输出"],
        ["Debug Console", "调试控制台"],
        ["Start Debugging", "启动调试"],
        ["Run Without Debugging", "运行但不调试"],
        ["Stop Debugging", "停止调试"],
        ["Restart Debugging", "重新启动调试"],
        ["Toggle Breakpoint", "切换断点"],
        ["Step Over", "单步跳过"],
        ["Step Into", "单步调试"],
        ["Step Out", "单步跳出"],
        ["Continue", "继续"],
        ["Toggle Primary Side Bar", "切换主侧栏"],
        ["Toggle Panel", "切换面板"],
        ["Toggle Terminal", "切换终端"],
        ["Toggle Panel Visibility", "切换面板可见性"],
        ["Toggle Side Bar Visibility", "切换侧栏可见性"],
        ["Toggle Activity Bar Visibility", "切换活动栏可见性"],
        ["Toggle Status Bar Visibility", "切换状态栏可见性"],
        ["Toggle Full Screen", "切换全屏"],
        ["Toggle Minimap", "切换小地图"],
        ["Toggle Breadcrumbs", "切换面包屑导航"],
        ["Toggle Word Wrap", "切换自动换行"],
        ["Toggle Developer Tools", "切换开发人员工具"],
        ["Split Editor", "拆分编辑器"],
        ["Join Editor Group", "合并编辑器组"],
        ["Move Editor into New Window", "将编辑器移动到新窗口"],
        ["Move Side Bar Left", "将侧栏移到左侧"],
        ["Move Side Bar Right", "将侧栏移到右侧"],
        ["Primary Side Bar", "主侧栏"],
        ["Secondary Side Bar", "辅助侧栏"],
        ["Panel Position", "面板位置"],
        ["Zen Mode", "禅模式"],
        ["Appearance", "外观"],
        ["Zoom In", "放大"],
        ["Zoom Out", "缩小"],
        ["Reset Zoom", "重置缩放"],
        ["Copy Path", "复制路径"],
        ["Copy Relative Path", "复制相对路径"],
        ["Reveal in File Explorer", "在文件资源管理器中显示"],
        ["Reveal in Finder", "在 Finder 中显示"],
        ["Reveal in Explorer", "在资源管理器中显示"],
        ["Open in Integrated Terminal", "在集成终端中打开"],
        ["Switch Window...", "切换窗口..."],
        ["Merge All Windows", "合并所有窗口"],
        ["Bring All to Front", "全部置于顶层"],
        ["Minimize", "最小化"],
        ["Zoom", "缩放"],
        ["Hide Others", "隐藏其他"],
        ["Show All", "显示全部"],
        ["Services", "服务"],
        ["Hide Cursor", "隐藏 Cursor"],
        ["Quit Cursor", "退出 Cursor"],
        ["About Cursor", "关于 Cursor"],
        ["Check for Updates", "检查更新"],
        ["Check for Updates...", "检查更新..."],
        ["Documentation", "文档"],
        ["Release Notes", "发行说明"],
        ["Report Issue", "报告问题"],
        ["Open Logs Folder", "打开日志文件夹"],
        ["Open Process Explorer", "打开进程资源管理器"],
        ["Configure Runtime Arguments", "配置运行时参数"],
        ["Cursor Settings", "Cursor 设置"],
        ["VS Code Settings", "VS Code 设置"],
        ["User Settings", "用户设置"],
        ["Workspace Settings", "工作区设置"],
        ["Folder Settings", "文件夹设置"],
        ["Open User Settings (JSON)", "打开用户设置 (JSON)"],
        ["Open Workspace Settings (JSON)", "打开工作区设置 (JSON)"],
        ["Preferences: Open Settings", "首选项：打开设置"],
        ["Preferences: Open Keyboard Shortcuts", "首选项：打开键盘快捷键"],
        ["Color Theme...", "颜色主题..."],
        ["File Icon Theme...", "文件图标主题..."],
        ["Product Icon Theme...", "产品图标主题..."],
        ["Install Local Extensions...", "安装本地扩展..."],
        ["Install from VSIX...", "从 VSIX 安装..."],
        ["Show Installed Extensions", "显示已安装的扩展"],
        ["Show Recommended Extensions", "显示推荐扩展"],
        ["Show Popular Extensions", "显示热门扩展"],
        ["Show Built-in Extensions", "显示内置扩展"],
        ["Enable All Extensions", "启用所有扩展"],
        ["Disable All Extensions", "禁用所有扩展"],
        ["Update All Extensions", "更新所有扩展"],
        ["Restart Extensions", "重启扩展"],
        ["Developer: Reload Window", "开发人员：重新加载窗口"],
        ["Show Explorer", "显示资源管理器"],
        ["Show Search", "显示搜索"],
        ["Show Source Control", "显示源代码管理"],
        ["Show Extensions", "显示扩展"],
        ["Show Run and Debug", "显示运行和调试"],
        ["Focus on Chat View", "聚焦聊天视图"],
        ["Open Chat", "打开聊天"],
        ["New Chat", "新建聊天"],
        ["Agent Layout", "智能体布局"],
        ["Editor Layout", "编辑器布局"],
        ["Activity Bar Position", "活动栏位置"],
        ["Arrange Icons", "排列图标"],
        ["Command Palette", "命令面板"],
        ["View License", "查看许可证"],
        ["More Actions...", "更多操作..."],
        ["Application Menu", "应用程序菜单"],
        ["Match Case", "区分大小写"],
        ["Match Whole Word", "全字匹配"],
        ["Use Regular Expression", "使用正则表达式"],
        ["Preserve Case", "保留大小写"],
        ["Type to search", "输入以搜索"],
        ["No results found.", "未找到结果。"],
        ["Collapse All", "全部折叠"],
        ["In Progress", "进行中"],
        ["Close Dialog", "关闭对话框"],

        // ==================== Command Palette ====================
        ["Search files, actions, agents...", "搜索文件、操作、智能体..."],
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
        [/^Updated (.+) ago$/i, "$1前更新"],
        [/^(\\d+) seconds? ago$/i, "$1 秒前"],
        [/^(\\d+) minutes? ago$/i, "$1 分钟前"],
        [/^(\\d+) hours? ago$/i, "$1 小时前"],
        [/^(\\d+) days? ago$/i, "$1 天前"],
        [/^Auto-Run Mode Disabled by Team Admin$/i, "自动运行模式已被团队管理员禁用"],
        [/^Auto-Run Mode Controlled by Team Admin$/i, "自动运行模式由团队管理员控制"],
        [/^Auto-Run Mode Controlled by Team Admin \\(Sandbox Enabled\\)$/i, "自动运行模式由团队管理员控制（沙盒已启用）"],
        [/^Custom cron: (.+)$/i, "自定义 Cron：$1"],
        [/^(.+) at (.+)$/i, "$1 于 $2"],
        [/^Automatically index any new folders with fewer than (\\d+) files$/i, "自动索引文件数少于 $1 的新文件夹"],
        [/^(\\d+) hooks?$/i, "$1 个钩子"],
        [/^(\\d+) automations?$/i, "$1 个自动化"],
        [/^(\\d+) rules?$/i, "$1 条规则"],
        [/^(\\d+) skills?$/i, "$1 个技能"],
        [/^(\\d+) commands?$/i, "$1 个命令"],
        [/^(\\d+) subagents?$/i, "$1 个子智能体"]
    ];

    // ================================================================
    // SECTION 2: 翻译引擎
    // ================================================================

    var TiaoGuo_XuanZeQi = '.monaco-editor, .overflow-guard, .view-lines, .editor-scrollable, .inputarea, .rename-input';
    var TiaoGuo_BiaoQian = new Set(['TEXTAREA', 'INPUT', 'SCRIPT', 'STYLE', 'CODE', 'PRE', 'NOSCRIPT']);

    function _GuiYi_WenBen(s) {
        return String(s || '')
            .replace(/[\\u00a0\\u2007\\u202f]/g, ' ')
            .replace(/\\u2026/g, '...')
            .replace(/^\\s*\\+\\s+/, '')
            .trim();
    }

    function _ChaZhao_FanYi(s) {
        if (!s) return null;
        if (FanYi_CiDian.has(s)) return FanYi_CiDian.get(s);
        var n = _GuiYi_WenBen(s);
        if (n && n !== s && FanYi_CiDian.has(n)) return FanYi_CiDian.get(n);
        return null;
    }

    function FanYi_WenBen_JieDian(node) {
        var text = node.textContent;
        if (!text) return;
        var trimmed = text.trim();
        if (!trimmed || trimmed.length > 500) return;
        if (/^[\\d\\s.,;:!?@#$%^&*()\\-+=<>\\/\\\\|~`'"[\\]{}]+$/.test(trimmed)) return;
        if (/[\\u4e00-\\u9fff]/.test(trimmed) && (trimmed.match(/[\\u4e00-\\u9fff]/g) || []).length > trimmed.length * 0.3) return;

        var yiWen = _ChaZhao_FanYi(trimmed);
        if (yiWen) {
            var prefix = text.substring(0, text.indexOf(trimmed));
            var suffix = text.substring(text.indexOf(trimmed) + trimmed.length);
            node.textContent = prefix + yiWen + suffix;
            return;
        }

        for (var i = 0; i < MoShi_FanYi.length; i++) {
            var pair = MoShi_FanYi[i];
            if (pair[0].test(trimmed)) {
                var result = trimmed.replace(pair[0], pair[1]);
                node.textContent = text.replace(trimmed, result);
                return;
            }
        }
    }

    function FanYi_ShuXing(el) {
        var attrs = ['title', 'aria-label', 'placeholder'];
        for (var i = 0; i < attrs.length; i++) {
            var val = el.getAttribute(attrs[i]);
            if (val) {
                var yiWen = _ChaZhao_FanYi(val.trim());
                if (yiWen) el.setAttribute(attrs[i], yiWen);
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
                if (node.id === 'cursor-yongliang-chat') continue;
                FanYi_ShuXing(node);
                if (node.shadowRoot) {
                    try { _GuaJie_YingZi(node); FanYi_ZiShu(node.shadowRoot); } catch (e) {}
                }
                var children = node.childNodes;
                for (var i = children.length - 1; i >= 0; i--) { stack.push(children[i]); }
            } else if (node.nodeType === Node.TEXT_NODE) {
                if (!Shi_BianJiQi_QuYu(node)) { FanYi_WenBen_JieDian(node); }
            }
        }
    }

    var DaiChuLi_JieDian = [];
    var YiDiaoDu = false;
    var GuanChaQi = null;

    function _GuaJie_YingZi(el) {
        if (!el || !el.shadowRoot || !GuanChaQi) return;
        try {
            GuanChaQi.observe(el.shadowRoot, { childList: true, subtree: true, characterData: true });
        } catch (e) {}
    }

    function TianJia_DaiChuLi(node) {
        DaiChuLi_JieDian.push(node);
        if (!YiDiaoDu) {
            YiDiaoDu = true;
            requestAnimationFrame(ZhiXing_PiLiang_FanYi);
        }
    }

    function ZhiXing_PiLiang_FanYi() {
        var nodes = DaiChuLi_JieDian;
        DaiChuLi_JieDian = [];
        YiDiaoDu = false;
        for (var i = 0; i < nodes.length; i++) {
            try { FanYi_ZiShu(nodes[i]); } catch (e) {}
        }
        try { ChaRu_YongLiang_XianShi(); } catch (e) {}
    }

    function GuanCha_HuiDiao(mutations) {
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
            } else if (m.type === 'characterData') {
                if (m.target.nodeType === Node.TEXT_NODE) {
                    TianJia_DaiChuLi(m.target);
                }
            }
        }
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

    function _GouZao_Cookie(lp) {
        try {
            var parts = lp.split('.');
            if (parts.length < 2) return null;
            var p = parts[1];
            while (p.length % 4) p += '=';
            var payload = JSON.parse(atob(p));
            var sub = (payload.sub || '').replace('auth0|', '');
            return sub + '::' + lp;
        } catch (e) { return null; }
    }

    function _JieXi_BaiFenFromMsg(msg) {
        if (!msg) return null;
        var m = String(msg).match(/([\\d]+(?:\\.[\\d]+)?)\\s*%/);
        return m ? Math.round(parseFloat(m[1]) * 10) / 10 : null;
    }

    function _YingYong_YongLiangShuJu(src) {
        if (!src || !src.youXiao) return false;
        if (src.summaryOk === false) return false;
        YONG_LIANG.zongYong = src.zongYong != null ? src.zongYong : YONG_LIANG.zongYong;
        YONG_LIANG.zongXian = src.zongXian != null ? src.zongXian : YONG_LIANG.zongXian;
        YONG_LIANG.shengYu = src.shengYu != null ? src.shengYu : YONG_LIANG.shengYu;
        YONG_LIANG.zongBaiFen = src.zongBaiFen != null ? src.zongBaiFen : YONG_LIANG.zongBaiFen;
        YONG_LIANG.shengYuBaiFen = src.shengYuBaiFen != null ? src.shengYuBaiFen : YONG_LIANG.shengYuBaiFen;
        YONG_LIANG.apiBaiFen = src.apiBaiFen != null ? src.apiBaiFen : YONG_LIANG.apiBaiFen;
        YONG_LIANG.autoBaiFen = src.autoBaiFen != null ? src.autoBaiFen : YONG_LIANG.autoBaiFen;
        YONG_LIANG.jiHua = src.jiHua || YONG_LIANG.jiHua;
        YONG_LIANG.jiFeiKaiShi = src.jiFeiKaiShi || YONG_LIANG.jiFeiKaiShi;
        YONG_LIANG.jiFeiJieShu = src.jiFeiJieShu || YONG_LIANG.jiFeiJieShu;
        YONG_LIANG.gengXinShiJian = src.gengXinShiJian || new Date().toLocaleString();
        YONG_LIANG.youXiao = true;
        return true;
    }

    function _JiaZai_LiveJson(huiDiao) {
        try {
            fetch('./usage_live.json?t=' + Date.now(), { cache: 'no-store' })
                .then(function(r) { return r.ok ? r.json() : null; })
                .then(function(data) {
                    if (data && _YingYong_YongLiangShuJu(data)) {
                        GengXin_KaPian();
                    }
                    if (huiDiao) huiDiao(!!data);
                })
                .catch(function() { if (huiDiao) huiDiao(false); });
        } catch (e) {
            if (huiDiao) huiDiao(false);
        }
    }

    function _JieXi_Summary(data) {
        if (!data || !data.individualUsage) return;
        var plan = data.individualUsage.plan || {};
        YONG_LIANG.zongYong = plan.used || 0;
        YONG_LIANG.zongXian = plan.limit || YONG_LIANG.zongXian || 2000;
        YONG_LIANG.shengYu = plan.remaining != null ? plan.remaining : Math.max(0, YONG_LIANG.zongXian - YONG_LIANG.zongYong);
        var zongFromPlan = plan.totalPercentUsed;
        var zongFromMsg = _JieXi_BaiFenFromMsg(data.autoModelSelectedDisplayMessage);
        YONG_LIANG.zongBaiFen = Math.round((zongFromPlan != null ? zongFromPlan : (zongFromMsg || 0)) * 10) / 10;
        YONG_LIANG.shengYuBaiFen = Math.round(Math.max(0, 100 - YONG_LIANG.zongBaiFen) * 10) / 10;
        var apiFromPlan = plan.apiPercentUsed;
        var apiFromMsg = _JieXi_BaiFenFromMsg(data.namedModelSelectedDisplayMessage);
        YONG_LIANG.apiBaiFen = Math.round((apiFromPlan != null ? apiFromPlan : (apiFromMsg || 0)) * 10) / 10;
        YONG_LIANG.autoBaiFen = Math.round((plan.autoPercentUsed || 0) * 10) / 10;
        YONG_LIANG.jiHua = data.membershipType || YONG_LIANG.jiHua;
        YONG_LIANG.youXiao = true;
        if (data.billingCycleStart) YONG_LIANG.jiFeiKaiShi = data.billingCycleStart.substring(0, 10);
        if (data.billingCycleEnd) YONG_LIANG.jiFeiJieShu = data.billingCycleEnd.substring(0, 10);
        YONG_LIANG.gengXinShiJian = new Date().toLocaleString();
    }

    function GengXin_KaPian() {
        var old = document.getElementById('cursor-yongliang-chat');
        if (old && old.parentElement) {
            var neo = ChuangJian_YongLiang_HengTiao();
            if (neo) old.parentElement.replaceChild(neo, old);
        }
        _YiChu_XuanFu();
        _YiChu_SheZhiKaPian();
    }

    function _YiChu_XuanFu() {
        var fl = document.getElementById('cursor-yongliang-float');
        if (fl && fl.parentElement) fl.parentElement.removeChild(fl);
    }

    function _YiChu_SheZhiKaPian() {
        var ka = document.getElementById('cursor-yongliang-settings');
        if (ka && ka.parentElement) ka.parentElement.removeChild(ka);
    }

    var _ZhengZaiShuaXin = false;

    function ShiShi_ShuaXin(ShiDianJi) {
        var lp = _JieMa();
        if (!lp || _ZhengZaiShuaXin) return;
        _ZhengZaiShuaXin = true;

        if (ShiDianJi) {
            var card = document.getElementById('cursor-yongliang-chat');
            if (card) card.style.opacity = '0.5';
        }

        var pending = 0;
        var wangZhanOk = false;
        function done() {
            pending--;
            if (pending <= 0) {
                _ZhengZaiShuaXin = false;
                YONG_LIANG._shiShi = true;
                if (!wangZhanOk) {
                    _JiaZai_LiveJson(function() { GengXin_KaPian(); });
                } else {
                    GengXin_KaPian();
                }
            }
        }

        var cookie = _GouZao_Cookie(lp);
        if (cookie) {
            pending++;
            try {
                var xhr1 = new XMLHttpRequest();
                xhr1.open('GET', 'https://www.cursor.com/api/usage-summary', true);
                xhr1.setRequestHeader('Cookie', 'WorkosCursorSessionToken=' + cookie);
                xhr1.setRequestHeader('Accept', 'application/json');
                xhr1.onload = function() {
                    if (xhr1.status === 200) {
                        try {
                            _JieXi_Summary(JSON.parse(xhr1.responseText));
                            wangZhanOk = true;
                        } catch (e) { console.log('[HanHua] summary parse', e); }
                    }
                    done();
                };
                xhr1.onerror = done;
                xhr1.send();
            } catch (e) { done(); }
        } else {
            pending++;
            _JiaZai_LiveJson(function() { done(); });
        }

        pending++;
        try {
            var xhr2 = new XMLHttpRequest();
            xhr2.open('GET', 'https://api2.cursor.sh/auth/usage', true);
            xhr2.setRequestHeader('Authorization', 'Bearer ' + lp);
            xhr2.setRequestHeader('Accept', 'application/json');
            xhr2.onload = function() {
                if (xhr2.status === 200) {
                    try {
                        var data = JSON.parse(xhr2.responseText);
                        if (data['gpt-4']) {
                            YONG_LIANG.gaoJiYong = data['gpt-4'].numRequests || 0;
                            var gxj = data['gpt-4'].maxRequestUsage;
                            if (gxj) YONG_LIANG.gaoJiXian = gxj;
                        }
                    } catch (e) { console.log('[HanHua] usage parse', e); }
                }
                done();
            };
            xhr2.onerror = done;
            xhr2.send();
        } catch (e) { done(); }

        if (pending === 0) _ZhengZaiShuaXin = false;
    }

    function _ce(tag, css, txt) {
        var e = document.createElement(tag);
        if (css) e.style.cssText = css;
        if (txt !== undefined && txt !== null) e.appendChild(document.createTextNode(txt));
        return e;
    }

    function _GeShi_BaiFen(v) {
        var n = Number(v);
        if (!isFinite(n)) return '0%';
        var r = Math.round(n * 10) / 10;
        return (r % 1 === 0 ? r.toFixed(0) : r.toFixed(1)) + '%';
    }

    function _YongLiang_YanSe() {
        var zP = typeof YONG_LIANG.zongBaiFen === 'number'
            ? YONG_LIANG.zongBaiFen
            : (YONG_LIANG.zongXian > 0 ? (YONG_LIANG.zongYong / YONG_LIANG.zongXian * 100) : 0);
        var gP = YONG_LIANG.gaoJiXian > 0 ? (YONG_LIANG.gaoJiYong / YONG_LIANG.gaoJiXian * 100) : 0;
        return {
            zP: zP, gP: gP,
            zC: zP < 60 ? '#4ade80' : (zP < 85 ? '#fbbf24' : '#ef4444'),
            gC: gP < 60 ? '#38bdf8' : (gP < 85 ? '#fbbf24' : '#ef4444')
        };
    }

    function _TianJia_XinXiKuai(rongQi, biaoQian, zhi, yanSe) {
        var kuai = _ce('span', 'display:inline-flex;align-items:center;gap:4px;margin-right:12px;white-space:nowrap;');
        kuai.appendChild(_ce('span', 'color:var(--vscode-descriptionForeground, #6b7280);font-size:11px;font-weight:500;', biaoQian));
        kuai.appendChild(_ce('span', 'color:' + (yanSe || 'var(--vscode-foreground, #e5e5e5)') + ';font-weight:600;font-size:11px;', zhi));
        rongQi.appendChild(kuai);
        return kuai;
    }

    function ChuangJian_YongLiang_HengTiao() {
        if (!YONG_LIANG || !YONG_LIANG.youXiao) return null;
        var ys = _YongLiang_YanSe();

        var W = _ce('div',
            'display:flex;align-items:center;flex-wrap:wrap;gap:2px 4px;' +
            'width:100%;box-sizing:border-box;' +
            'margin:6px 0 0 0;padding:6px 10px;' +
            'border-radius:8px;' +
            'background:var(--vscode-editorWidget-background, rgba(128,128,128,0.08));' +
            'border:1px solid var(--vscode-widget-border, rgba(128,128,128,0.18));' +
            'font-size:11px;line-height:18px;' +
            'color:var(--vscode-foreground, #e5e5e5);' +
            'cursor:pointer;user-select:none;transition:opacity 0.3s;'
        );
        W.id = 'cursor-yongliang-chat';
        W.setAttribute('aria-label', '\\u7528\\u91cf\\u76d1\\u63a7');
        W.setAttribute('title', '\\u70b9\\u51fb\\u5237\\u65b0\\u7528\\u91cf');

        _TianJia_XinXiKuai(W, '\\u5408\\u8ba1', _GeShi_BaiFen(YONG_LIANG.zongBaiFen), ys.zC);
        _TianJia_XinXiKuai(W, '\\u5269\\u4f59', _GeShi_BaiFen(YONG_LIANG.shengYuBaiFen), '#4ade80');
        if (YONG_LIANG.autoBaiFen !== undefined && YONG_LIANG.autoBaiFen !== null) {
            _TianJia_XinXiKuai(W, 'Auto', _GeShi_BaiFen(YONG_LIANG.autoBaiFen), '#a78bfa');
        }
        if (YONG_LIANG.apiBaiFen !== undefined && YONG_LIANG.apiBaiFen !== null) {
            _TianJia_XinXiKuai(W, 'API', _GeShi_BaiFen(YONG_LIANG.apiBaiFen), '#38bdf8');
        }
        if (YONG_LIANG.jiFeiJieShu) {
            _TianJia_XinXiKuai(W, '\\u91cd\\u7f6e', YONG_LIANG.jiFeiJieShu, '#7c3aed');
        }

        W.addEventListener('click', function(e) { e.preventDefault(); e.stopPropagation(); ShiShi_ShuaXin(true); });
        return W;
    }

    function _ShiKeJian(el) {
        if (!el || !(el instanceof Element)) return false;
        if (el.offsetParent === null && getComputedStyle(el).position !== 'fixed') return false;
        var r = el.getBoundingClientRect();
        return r.width >= 60 && r.height >= 8;
    }

    function _ZhaoDao_ShuRuKuang() {
        var xuanZeQi = [
            '.ai-input-full-input-box.full-input-box',
            '.full-input-box',
            '.composer-input-container',
            '.composer-input-wrapper',
            '.ui-prompt-input',
            '.aislash-editor-input'
        ];
        var houXuan = [];
        for (var i = 0; i < xuanZeQi.length; i++) {
            var nodes = document.querySelectorAll(xuanZeQi[i]);
            for (var j = 0; j < nodes.length; j++) {
                var el = nodes[j];
                if (!_ShiKeJian(el)) continue;
                // 跳过只读预览输入
                if (el.classList && el.classList.contains('aislash-editor-input-readonly')) continue;
                var box = el.closest('.ai-input-full-input-box, .full-input-box, .composer-input-container, .composer-input-wrapper, .ui-prompt-input') || el;
                if (!_ShiKeJian(box)) box = el;
                var r = box.getBoundingClientRect();
                houXuan.push({ el: box, top: r.top, bottom: r.bottom, area: r.width * r.height });
            }
        }
        if (!houXuan.length) return null;
        // 优先选靠近窗口底部的输入框（聊天输入通常在底部）
        houXuan.sort(function(a, b) {
            if (Math.abs(b.bottom - a.bottom) > 20) return b.bottom - a.bottom;
            return b.area - a.area;
        });
        return houXuan[0].el;
    }

    function _ChaRu_DuiHuaLan() {
        var shuRu = _ZhaoDao_ShuRuKuang();
        var existing = document.getElementById('cursor-yongliang-chat');

        if (!shuRu) return !!existing;

        // 已正确插在输入框正下方则保留
        if (existing && existing.parentElement && existing.previousElementSibling === shuRu) {
            return true;
        }

        var tiao = ChuangJian_YongLiang_HengTiao();
        if (!tiao) return false;

        if (existing && existing.parentElement) {
            existing.parentElement.removeChild(existing);
        }

        if (shuRu.parentElement) {
            // 插在输入框下方：上方会被 Changes/Push 等动态操作按钮遮挡
            shuRu.parentElement.insertBefore(tiao, shuRu.nextSibling);
            console.log('[HanHua] Usage bar inserted below input');
            return true;
        }
        return false;
    }

    function ChaRu_YongLiang_XianShi() {
        if (!YONG_LIANG || !YONG_LIANG.youXiao) return;
        _YiChu_XuanFu();
        _YiChu_SheZhiKaPian();
        _ChaRu_DuiHuaLan();
    }

    // ================================================================
    // SECTION 4: 初始化
    // ================================================================

    function ChuShiHua() {
        var target = document.documentElement || document.body;
        if (!target) { setTimeout(ChuShiHua, 50); return; }

        GuanChaQi = new MutationObserver(GuanCha_HuiDiao);
        GuanChaQi.observe(target, { childList: true, subtree: true, characterData: true });

        setTimeout(function() {
            if (document.body) {
                FanYi_ZiShu(document.body);
                ChaRu_YongLiang_XianShi();
                _JiaZai_LiveJson(function() {
                    ChaRu_YongLiang_XianShi();
                    if (_XHJ_LP) { setTimeout(function() { ShiShi_ShuaXin(false); }, 800); }
                });
            }
        }, 500);

        var BuFan_CiShu = 0;
        var BuFan_JiShiQi = setInterval(function() {
            BuFan_CiShu++;
            if (document.body) {
                FanYi_ZiShu(document.body);
                ChaRu_YongLiang_XianShi();
            }
            if (BuFan_CiShu >= 10) { clearInterval(BuFan_JiShiQi); }
        }, 3000);

        if (_XHJ_LP) {
            setInterval(function() {
                _JiaZai_LiveJson(function() {
                    if (document.getElementById('cursor-yongliang-chat')) {
                        ShiShi_ShuaXin(false);
                    }
                });
            }, 20000);
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
    return os.path.join(HuoQu_AnZhuang_LuJing(), GONG_ZUO_TAI_HTML_XIANG_DUI)


def HuoQu_HTML_LuJing():
    """获取 workbench.html 完整路径"""
    return os.path.join(HuoQu_GongZuoTai_LuJing(), GONG_ZUO_TAI_HTML_MING)


def HuoQu_JS_LuJing():
    """获取翻译 JS 文件完整路径"""
    return os.path.join(HuoQu_GongZuoTai_LuJing(), HAN_HUA_JS_MING)


def HuoQu_Live_JSON_LuJing():
    """获取实时用量 JSON 文件路径（与 workbench 同目录，JS 可同源 fetch）"""
    return os.path.join(HuoQu_GongZuoTai_LuJing(), YONG_LIANG_LIVE_JSON)


def HuoQu_BeiFen_LuJing():
    """获取备份文件路径"""
    return HuoQu_HTML_LuJing() + BEI_FEN_HOU_ZHUI


# ============================================================
# ★★★ 版本检测与状态持久化（应对 Cursor 更新覆盖） ★★★
# ============================================================

def HuoQu_ZhuangTai_MuLu():
    """获取本工具在用户目录下的状态目录"""
    LuJing = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), ZHUANG_TAI_MU_LU_MING)
    os.makedirs(LuJing, exist_ok=True)
    return LuJing


def HuoQu_ZhuangTai_WenJian():
    """获取注入状态文件路径"""
    return os.path.join(HuoQu_ZhuangTai_MuLu(), ZHUANG_TAI_WEN_JIAN_MING)


def HuoQu_Cursor_BanBen():
    """读取当前 Cursor 版本与 commit，用于判断是否刚更新过"""
    LuJing_Product = os.path.join(HuoQu_AnZhuang_LuJing(), "resources", "app", "product.json")
    JieGuo = {"version": "", "commit": "", "htmlMtime": 0}
    if os.path.exists(LuJing_Product):
        try:
            with open(LuJing_Product, 'r', encoding='utf-8') as WenJian:
                ShuJu = json.load(WenJian)
            JieGuo["version"] = str(ShuJu.get("version") or "")
            JieGuo["commit"] = str(ShuJu.get("commit") or "")
        except Exception:
            pass
    LuJing_Html = HuoQu_HTML_LuJing()
    if os.path.exists(LuJing_Html):
        try:
            JieGuo["htmlMtime"] = int(os.path.getmtime(LuJing_Html))
        except Exception:
            pass
    return JieGuo


def DuQu_ZhuRu_ZhuangTai():
    """读取上次成功注入时记录的版本信息"""
    LuJing = HuoQu_ZhuangTai_WenJian()
    if not os.path.exists(LuJing):
        return {}
    try:
        with open(LuJing, 'r', encoding='utf-8') as WenJian:
            return json.load(WenJian)
    except Exception:
        return {}


def XieRu_ZhuRu_ZhuangTai():
    """写入当前注入成功对应的 Cursor 版本指纹"""
    BanBen = HuoQu_Cursor_BanBen()
    ZhuangTai = {
        "version": BanBen.get("version", ""),
        "commit": BanBen.get("commit", ""),
        "htmlMtime": BanBen.get("htmlMtime", 0),
        "installPath": HuoQu_AnZhuang_LuJing(),
        "updatedAt": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    with open(HuoQu_ZhuangTai_WenJian(), 'w', encoding='utf-8') as WenJian:
        json.dump(ZhuangTai, WenJian, ensure_ascii=False, indent=2)
    return ZhuangTai


def JianCha_JS_CunZai():
    """检查翻译脚本文件是否存在"""
    return os.path.exists(HuoQu_JS_LuJing())


def XuYao_ChongXin_ZhuRu():
    """
    判断是否需要重新注入。
    Cursor 更新后通常会：覆盖 workbench.html、删除 cursor_hanhua.js、更换 product.json。
    """
    if not JianCha_YiZhuRu():
        return True, "workbench.html 中未发现汉化注入标记"
    if not JianCha_JS_CunZai():
        return True, "cursor_hanhua.js 缺失"
    DangQian = HuoQu_Cursor_BanBen()
    ShangCi = DuQu_ZhuRu_ZhuangTai()
    if not ShangCi:
        return True, "尚未记录注入版本（首次自愈）"
    if ShangCi.get("version") != DangQian.get("version") or ShangCi.get("commit") != DangQian.get("commit"):
        return True, f"检测到 Cursor 已更新: {ShangCi.get('version')} → {DangQian.get('version')}"
    if ShangCi.get("installPath") and ShangCi.get("installPath") != HuoQu_AnZhuang_LuJing():
        return True, "检测到 Cursor 安装路径变化"
    return False, "汉化注入完好"


def HuoQu_ZhuoMian_LuJing():
    """获取桌面目录"""
    ZhuoMian = os.path.join(os.path.expanduser("~"), "Desktop")
    if not os.path.isdir(ZhuoMian):
        ZhuoMian = os.path.join(os.environ.get("USERPROFILE", ""), "Desktop")
    return ZhuoMian


def HuoQu_PythonW():
    """优先返回无控制台窗口的 pythonw"""
    Python_Exe = sys.executable
    PythonW = Python_Exe.replace("python.exe", "pythonw.exe")
    if os.path.exists(PythonW):
        return PythonW
    return Python_Exe


def QiDong_Cursor():
    """启动 Cursor（不等待退出）"""
    Cursor_Exe = os.path.join(HuoQu_AnZhuang_LuJing(), "Cursor.exe")
    if not os.path.exists(Cursor_Exe):
        raise FileNotFoundError(f"未找到 Cursor: {Cursor_Exe}")
    YongHu_ShuJu = HuoQu_ShuJu_LuJing()
    CaoZuoXiTong = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    subprocess.Popen(
        [Cursor_Exe, f"--user-data-dir={YongHu_ShuJu}"],
        cwd=os.path.dirname(Cursor_Exe),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=CaoZuoXiTong,
    )


def _YongLiang_JianKong_Suo():
    return os.path.join(HuoQu_ZhuangTai_MuLu(), "usage_watch.pid")


def _JinCheng_HuoZhe(pid):
    if not pid or pid <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, int(pid))
        if handle:
            kernel32.CloseHandle(handle)
            return True
    except Exception:
        pass
    return False


def Shi_Cursor_YunXing():
    """检测 Cursor 主进程是否仍在运行"""
    Ming = "Cursor.exe"
    try:
        JieGuo = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {Ming}", "/NH"],
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
        )
        WenBen = (JieGuo.stdout or "") + (JieGuo.stderr or "")
        return Ming.lower() in WenBen.lower() and "no tasks" not in WenBen.lower()
    except Exception:
        return True


def QiDong_YongLiang_JianKong():
    """后台启动用量刷新（Cursor 运行期间定时更新 usage_live.json）"""
    Suo = _YongLiang_JianKong_Suo()
    if os.path.exists(Suo):
        try:
            with open(Suo, "r", encoding="utf-8") as WenJian:
                Jiu_Pid = int((WenJian.read() or "").strip())
            if _JinCheng_HuoZhe(Jiu_Pid):
                return
        except Exception:
            pass

    BenJiaoBen = os.path.abspath(__file__)
    PythonW = HuoQu_PythonW()
    CaoZuoXiTong = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    subprocess.Popen(
        [PythonW, BenJiaoBen, "--usage-watch"],
        cwd=os.path.dirname(BenJiaoBen),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=CaoZuoXiTong,
    )


def YongLiang_JianKong_Loop():
    """Cursor 运行期间定时拉取官网用量并写入 usage_live.json。

    只写 live json，不重写汉化 JS（页面通过同源 fetch 刷新）。
    启动后先等 Cursor 出现，避免 --qi-dong 竞态导致监控立刻退出。
    """
    Suo = _YongLiang_JianKong_Suo()
    os.makedirs(os.path.dirname(Suo), exist_ok=True)
    with open(Suo, "w", encoding="utf-8") as WenJian:
        WenJian.write(str(os.getpid()))
    try:
        for _ in range(90):
            if Shi_Cursor_YunXing():
                break
            time.sleep(1)
        LianXu_WeiYunXing = 0
        while LianXu_WeiYunXing < 20:
            if Shi_Cursor_YunXing():
                LianXu_WeiYunXing = 0
                try:
                    GengXin_YongLiang_XianShi(JingMo=True, JinXieLive=True)
                except Exception:
                    pass
                for _ in range(20):
                    if not Shi_Cursor_YunXing():
                        break
                    time.sleep(1)
            else:
                LianXu_WeiYunXing += 1
                time.sleep(1)
    finally:
        try:
            if os.path.exists(Suo):
                os.remove(Suo)
        except Exception:
            pass


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


def ChuangJian_BeiFen(QiangZhi=False):
    """
    创建 workbench.html / product.json 备份。
    Cursor 更新后旧备份会过期，因此：
    - 当前 HTML 未注入时，始终用当前干净文件覆盖备份
    - 版本变化或强制时同样刷新备份
    """
    LuJing_Html = HuoQu_HTML_LuJing()
    LuJing_BeiFen = HuoQu_BeiFen_LuJing()
    XuYao_ShuaXin = QiangZhi or (not JianCha_YiZhuRu()) or (not os.path.exists(LuJing_BeiFen))

    if XuYao_ShuaXin:
        shutil.copy2(LuJing_Html, LuJing_BeiFen)
        print(f"[备份] 已刷新 HTML 备份: {LuJing_BeiFen}")
    else:
        print(f"[备份] HTML 备份已存在: {LuJing_BeiFen}")

    LuJing_Product = os.path.join(HuoQu_AnZhuang_LuJing(), "resources", "app", "product.json")
    LuJing_Product_BeiFen = LuJing_Product + BEI_FEN_HOU_ZHUI
    if os.path.exists(LuJing_Product) and (QiangZhi or XuYao_ShuaXin or not os.path.exists(LuJing_Product_BeiFen)):
        # 仅在尚未注入时备份 product.json，避免把已改校验值当成“原始”
        if not JianCha_YiZhuRu() or not os.path.exists(LuJing_Product_BeiFen) or QiangZhi:
            shutil.copy2(LuJing_Product, LuJing_Product_BeiFen)
            print(f"[备份] 已刷新 product.json 备份: {LuJing_Product_BeiFen}")


def XieRu_FanYi_JS(YongLiang_ShuJu, LingPai=""):
    """将翻译 + 用量 JavaScript 文件写入 Cursor 目录"""
    LuJing_Js = HuoQu_JS_LuJing()
    JS_NeiRong = ShengCheng_JS_DaiMa(YongLiang_ShuJu, LingPai)
    with open(LuJing_Js, 'w', encoding='utf-8') as WenJian:
        WenJian.write(JS_NeiRong)
    XieRu_YongLiang_LiveJson(YongLiang_ShuJu)
    print(f"[写入] 脚本已写入: {LuJing_Js}")


def XieRu_YongLiang_LiveJson(YongLiang_ShuJu):
    """写入实时用量 JSON，供运行中的 Cursor 通过同源 fetch 刷新显示"""
    if not YongLiang_ShuJu:
        return
    Jiu = DuQu_YongLiang_LiveJson()
    if BuYing_Gai_FuGai_LiveJson(YongLiang_ShuJu, Jiu):
        return
    LuJing = HuoQu_Live_JSON_LuJing()
    with open(LuJing, 'w', encoding='utf-8') as WenJian:
        json.dump(YongLiang_ShuJu, WenJian, ensure_ascii=False, indent=2)


def ZhuRu_HTML():
    """在 workbench.html 中注入脚本引用（幂等：已注入则跳过）"""
    LuJing_Html = HuoQu_HTML_LuJing()
    with open(LuJing_Html, 'r', encoding='utf-8') as WenJian:
        NeiRong = WenJian.read()

    if ZHU_RU_BIAO_JI in NeiRong and HAN_HUA_JS_MING in NeiRong:
        print("[注入] workbench.html 已包含脚本引用，跳过重复注入")
        GengXin_JiaoYan_Zhi()
        return

    # 若残留半截注入，先清理再写入
    if ZHU_RU_BIAO_JI in NeiRong or HAN_HUA_JS_MING in NeiRong:
        HangLieBiao = NeiRong.splitlines(keepends=True)
        XinHang = []
        TiaoGuo = False
        for Hang in HangLieBiao:
            if ZHU_RU_BIAO_JI in Hang:
                TiaoGuo = True
                continue
            if TiaoGuo and f'src="./{HAN_HUA_JS_MING}"' in Hang:
                TiaoGuo = False
                continue
            if f'src="./{HAN_HUA_JS_MING}"' in Hang:
                continue
            if not TiaoGuo:
                XinHang.append(Hang)
        NeiRong = ''.join(XinHang)

    ZhuRu_DaiMa = f'\n\t{ZHU_RU_BIAO_JI}\n\t<script src="./{HAN_HUA_JS_MING}"></script>\n'

    if '</html>' in NeiRong:
        # 放在 </html> 前，兼容部分版本 </body> 后仍有内容的结构
        NeiRong = NeiRong.replace('</html>', f'{ZhuRu_DaiMa}</html>')
    elif '</body>' in NeiRong:
        NeiRong = NeiRong.replace('</body>', f'</body>\n{ZhuRu_DaiMa}')
    else:
        NeiRong = NeiRong + ZhuRu_DaiMa

    with open(LuJing_Html, 'w', encoding='utf-8') as WenJian:
        WenJian.write(NeiRong)

    print(f"[注入] 已在 workbench.html 中注入脚本引用")
    GengXin_JiaoYan_Zhi()


def GengXin_JiaoYan_Zhi():
    """更新 product.json 中 workbench.html 的校验哈希值"""
    LuJing_Product = os.path.join(HuoQu_AnZhuang_LuJing(), "resources", "app", "product.json")
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


def HuiFu_JiaoYan_Zhi():
    """恢复 product.json 的原始校验值"""
    LuJing_Product = os.path.join(HuoQu_AnZhuang_LuJing(), "resources", "app", "product.json")
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

    ZhuangTai = HuoQu_ZhuangTai_WenJian()
    if os.path.exists(ZhuangTai):
        os.remove(ZhuangTai)

    print("[完成] 已恢复原始状态")


def ShouJi_YongLiang_ShuJu(JingMo=False):
    """读取令牌并整理用量数据，失败时返回占位数据"""
    if not JingMo:
        print("\n[步骤] 读取认证信息...")
    LingPai, YouXiang = DuQu_FangWen_LingPai()
    if LingPai:
        if not JingMo:
            print(f"[认证] 已找到令牌，邮箱: {YouXiang or '未知'}")
    else:
        if not JingMo:
            print("[认证] 未找到认证令牌，将跳过用量获取（仅汉化）")

    YongLiang_ShuJu = None
    if LingPai:
        if not JingMo:
            print("[步骤] 获取用量数据...")
        YongLiang_ShuJu = ZhengHe_YongLiang_ShuJu(LingPai)
        if YongLiang_ShuJu and YongLiang_ShuJu.get("youXiao"):
            if not JingMo:
                print(f"[用量] 合计: {YongLiang_ShuJu['zongBaiFen']}%  剩余: {YongLiang_ShuJu['shengYuBaiFen']}%")
                print(f"[用量] Auto: {YongLiang_ShuJu['autoBaiFen']}%  API: {YongLiang_ShuJu['apiBaiFen']}%")
                if YongLiang_ShuJu.get('jiFeiKaiShi'):
                    print(f"[用量] 计费周期: {YongLiang_ShuJu['jiFeiKaiShi']} 至 {YongLiang_ShuJu['jiFeiJieShu']}")
        else:
            if not JingMo:
                print("[用量] 获取用量数据失败，将仅汉化")
            YongLiang_ShuJu = None

    if not YongLiang_ShuJu:
        YongLiang_ShuJu = {
            "zongYong": 0, "zongXian": 0, "shengYu": 0,
            "gaoJiYong": 0, "gaoJiXian": 0,
            "zongBaiFen": 0, "shengYuBaiFen": 100, "apiBaiFen": 0, "autoBaiFen": 0,
            "jiFeiKaiShi": "", "jiFeiJieShu": "",
            "gengXinShiJian": "", "jiHua": "", "youXiao": False, "summaryOk": False
        }
    return YongLiang_ShuJu, LingPai or ""


def ZhiXing_ZhuRu(YongLiang_ShuJu, LingPai, QiangZhi_BeiFen=False):
    """执行备份 + 写 JS + 注入 HTML + 记录版本"""
    print("[步骤] 创建/刷新备份并写入脚本...")
    ChuangJian_BeiFen(QiangZhi=QiangZhi_BeiFen)
    XieRu_FanYi_JS(YongLiang_ShuJu, LingPai)
    print("[步骤] 注入 HTML 引用...")
    ZhuRu_HTML()
    ZhuangTai = XieRu_ZhuRu_ZhuangTai()
    print(f"[状态] 已记录注入版本: {ZhuangTai.get('version')} ({ZhuangTai.get('commit', '')[:8]})")


def GengXin_YongLiang_XianShi(JingMo=False, JinXieLive=False):
    """拉取最新用量并写入 live json；非监控周期还会回写注入脚本。"""
    YongLiang_ShuJu, LingPai = ShouJi_YongLiang_ShuJu(JingMo=JingMo)
    Jiu = DuQu_YongLiang_LiveJson()
    if not YongLiang_ShuJu_KeXin(YongLiang_ShuJu) and YongLiang_ShuJu_KeXin(Jiu):
        if not JingMo:
            print("[用量] 本次拉取未拿到官网百分比，保留上次有效数据")
        return Jiu
    XieRu_YongLiang_LiveJson(YongLiang_ShuJu)
    if (not JinXieLive) and JianCha_YiZhuRu() and YongLiang_ShuJu_KeXin(YongLiang_ShuJu):
        XieRu_FanYi_JS(YongLiang_ShuJu, LingPai)
        GengXin_JiaoYan_Zhi()
    return YongLiang_ShuJu if YongLiang_ShuJu_KeXin(YongLiang_ShuJu) else (Jiu or YongLiang_ShuJu)


def QueBao_ZhuRu(JingMo=False):
    """
    确保汉化有效：若 Cursor 更新导致注入丢失，则自动重新注入。
    返回: (是否执行了修复, 说明文字)
    """
    XuYao, YuanYin = XuYao_ChongXin_ZhuRu()

    if XuYao:
        if not JingMo:
            print(f"[检测] 需要重新注入：{YuanYin}")
        YongLiang_ShuJu, LingPai = ShouJi_YongLiang_ShuJu(JingMo=JingMo)
        ZhiXing_ZhuRu(YongLiang_ShuJu, LingPai, QiangZhi_BeiFen=True)
        try:
            if Shi_Cursor_YunXing():
                QiDong_YongLiang_JianKong()
        except Exception:
            pass
        return True, YuanYin

    if not JingMo:
        print(f"[检测] {YuanYin}，刷新用量数据...")
    GengXin_YongLiang_XianShi(JingMo=JingMo)
    XieRu_ZhuRu_ZhuangTai()
    try:
        XieRu_QiDong_VBS()
    except Exception:
        pass
    try:
        if Shi_Cursor_YunXing():
            QiDong_YongLiang_JianKong()
    except Exception:
        pass
    return False, YuanYin


def QingLi_Jiu_JiHua_RenWu():
    """清理旧版定时/登录计划任务与启动项（不再使用）"""
    for Ming in (JI_HUA_REN_WU_MING, JI_HUA_REN_WU_MING + "OnLogon"):
        subprocess.run(["schtasks", "/Delete", "/F", "/TN", Ming], capture_output=True, text=True)
    QiDong_Lnk = os.path.join(
        os.environ.get("APPDATA", ""),
        r"Microsoft\Windows\Start Menu\Programs\Startup",
        "CursorChineseAutoHeal.lnk",
    )
    if os.path.exists(QiDong_Lnk):
        os.remove(QiDong_Lnk)
    Jiu_Bat = os.path.join(HuoQu_ZhuangTai_MuLu(), "auto_heal.bat")
    if os.path.exists(Jiu_Bat):
        os.remove(Jiu_Bat)


def XieRu_QiDong_VBS():
    """写入无窗口启动器：后台自愈后启动 Cursor"""
    BenJiaoBen = os.path.abspath(__file__)
    XiangMu_MuLu = os.path.dirname(BenJiaoBen)
    Vbs_LuJing = os.path.join(XiangMu_MuLu, QI_DONG_VBS_MING)
    PythonW = HuoQu_PythonW()
    # VBS 字符串内用 "" 表示引号；路径保持单反斜杠
    NeiRong = "\r\n".join([
        'Set sh = CreateObject("WScript.Shell")',
        f'sh.Run """{PythonW}"" ""{BenJiaoBen}"" --qi-dong", 0, True',
        "",
    ])
    with open(Vbs_LuJing, "w", encoding="ascii", errors="replace") as WenJian:
        WenJian.write(NeiRong)
    return Vbs_LuJing


def AnZhuang_ZiDong_XiuFu():
    """安装「仅启动时后台检查」：桌面快捷方式，无弹窗、无定时任务"""
    if os.name != 'nt':
        print("[错误] 自动启动检查目前仅支持 Windows")
        return False

    print("\n[安装] 正在清理旧版定时任务...")
    QingLi_Jiu_JiHua_RenWu()
    print("[安装] 正在确保当前汉化有效...")
    QueBao_ZhuRu(JingMo=False)

    Vbs_LuJing = XieRu_QiDong_VBS()
    print(f"[安装] 已写入无窗口启动器: {Vbs_LuJing}")

    ZhuoMian = HuoQu_ZhuoMian_LuJing()
    Lnk_LuJing = os.path.join(ZhuoMian, ZHUO_MIAN_KUAI_JIE_MING)
    Cursor_Exe = os.path.join(HuoQu_AnZhuang_LuJing(), "Cursor.exe")
    Ps = f'''
$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut('{Lnk_LuJing.replace("'", "''")}')
$lnk.TargetPath = 'wscript.exe'
$lnk.Arguments = '//nologo "{Vbs_LuJing.replace("'", "''")}"'
$lnk.WorkingDirectory = '{os.path.dirname(Vbs_LuJing).replace("'", "''")}'
$lnk.WindowStyle = 7
if (Test-Path '{Cursor_Exe.replace("'", "''")}') {{ $lnk.IconLocation = '{Cursor_Exe.replace("'", "''")},0' }}
$lnk.Description = '启动 Cursor（后台静默检查汉化，无弹窗）'
$lnk.Save()
'''
    subprocess.run(["powershell", "-NoProfile", "-Command", Ps], capture_output=True, text=True)
    if os.path.exists(Lnk_LuJing):
        print(f"[安装] 已创建桌面快捷方式: {Lnk_LuJing}")
    else:
        print("[警告] 桌面快捷方式创建失败，请直接使用 QiDong_Cursor_ZhongWen.vbs")

    print("\n[完成] 已改为「仅启动时后台检查」。")
    print("  - 请用桌面「Cursor中文」启动（无黑框、无弹窗）")
    print("  - 每次启动会先在后台检查/修复汉化，再打开 Cursor")
    print("  - 已移除每 5 分钟定时任务与开机自启检查")
    return True


def XieZai_ZiDong_XiuFu():
    """卸载桌面快捷方式与旧计划任务"""
    if os.name != 'nt':
        print("[错误] 仅支持 Windows")
        return False

    QingLi_Jiu_JiHua_RenWu()
    print("[卸载] 已清理旧版计划任务/启动项")

    Lnk_LuJing = os.path.join(HuoQu_ZhuoMian_LuJing(), ZHUO_MIAN_KUAI_JIE_MING)
    if os.path.exists(Lnk_LuJing):
        os.remove(Lnk_LuJing)
        print(f"[卸载] 已删除桌面快捷方式: {Lnk_LuJing}")

    print("[完成] 启动检查快捷方式已卸载（汉化文件本身未删除，可用 --huifu 完全恢复）")
    return True


# ============================================================
# ★★★ 主程序 ★★★
# ============================================================

def ZhuChengXu():
    """主程序入口"""
    CaoZuo = sys.argv[1] if len(sys.argv) > 1 else ""
    JingMo = CaoZuo in ("--xiu-fu", "--qi-dong", "--usage-watch")

    if JingMo:
        # 完全静默：无控制台输出、无弹窗
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
        sys.stderr = open(os.devnull, "w", encoding="utf-8")

    if not JingMo:
        print("=" * 60)
        print("  Cursor 汉化 + 用量监控工具")
        print(f"  工具版本: {GONG_JU_BAN_BEN}")
        print(f"  时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  安装路径: {HuoQu_AnZhuang_LuJing()}")
        print(f"  数据路径: {HuoQu_ShuJu_LuJing()}")
        BanBen = HuoQu_Cursor_BanBen()
        if BanBen.get("version"):
            print(f"  Cursor 版本: {BanBen.get('version')}")
        print("=" * 60)

    if CaoZuo == '--huifu':
        print("\n[模式] 恢复原始文件...")
        HuiFu_YuanShi()
        return

    if CaoZuo == '--an-zhuang':
        AnZhuang_ZiDong_XiuFu()
        return

    if CaoZuo == '--xie-zai':
        XieZai_ZiDong_XiuFu()
        return

    # 检查 Cursor 安装目录
    LuJing_Html = HuoQu_HTML_LuJing()
    if not os.path.exists(LuJing_Html):
        if not JingMo:
            print(f"\n[错误] 未找到 workbench.html: {LuJing_Html}")
            print(f"[提示] 请检查 CURSOR_AN_ZHUANG_LU_JING 是否正确: {HuoQu_AnZhuang_LuJing()}")
        sys.exit(1)

    # 后台静默：仅检查/修复
    if CaoZuo == '--xiu-fu':
        try:
            QueBao_ZhuRu(JingMo=True)
            sys.exit(0)
        except Exception:
            sys.exit(1)

    # 后台静默：检查/修复后启动 Cursor
    if CaoZuo == '--qi-dong':
        try:
            QueBao_ZhuRu(JingMo=True)
            QiDong_Cursor()
            QiDong_YongLiang_JianKong()
            sys.exit(0)
        except Exception:
            try:
                QiDong_Cursor()
            except Exception:
                pass
            sys.exit(1)

    # 后台静默：Cursor 运行期间定时刷新用量
    if CaoZuo == '--usage-watch':
        try:
            YongLiang_JianKong_Loop()
            sys.exit(0)
        except Exception:
            sys.exit(1)

    print("\n[模式] 检测并确保汉化有效（兼容 Cursor 版本更新）...")
    YiXiuFu, YuanYin = QueBao_ZhuRu(JingMo=False)

    print("\n" + "=" * 60)
    if YiXiuFu:
        print("  [完成] 已重新注入汉化（Cursor 更新后自动修复）！")
        print(f"  原因: {YuanYin}")
    else:
        print("  [完成] 汉化已是最新状态！")
    print("  请重启 Cursor 以查看效果。")
    print("  推荐执行一次: python CursorHanHua_GongJu.py --an-zhuang")
    print("  之后用桌面「Cursor中文」启动即可（启动时后台静默检查）。")
    print("  如需恢复英文: python CursorHanHua_GongJu.py --huifu")
    print("=" * 60)


if __name__ == '__main__':
    ZhuChengXu()
