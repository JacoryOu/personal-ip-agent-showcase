# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

# Curated fallback mock data for major platforms
FALLBACK_TOPICS = {
    "weibo": [
        {
            "title": "DeepSeek发布开源多模态智能体架构",
            "hot_value": 4892000,
            "platform": "weibo",
            "category": "AI",
            "summary": "国内AI领域再度迎来重磅开源，新架构大幅降低推理成本与落地门槛，受到全球开发者广泛探讨。",
            "url": "https://s.weibo.com/weibo?q=DeepSeek"
        },
        {
            "title": "AI时代独立开发者的一人公司浪潮",
            "hot_value": 3510000,
            "platform": "weibo",
            "category": "独立开发",
            "summary": "越来越多工程师与创作者借助大模型工具链实现独立商业化盈利，一人年入百万并非个例。",
            "url": "https://s.weibo.com/weibo?q=AI独立开发"
        },
        {
            "title": "2026数字化商业新风口与新逻辑",
            "hot_value": 2940000,
            "platform": "weibo",
            "category": "商业",
            "summary": "传统实体与私域生态正在被认知智能体深度重构，降本增效成为企业核心诉求。",
            "url": "https://s.weibo.com/weibo?q=商业新风口"
        },
        {
            "title": "十款彻底改变生产力的AI效率工具大盘点",
            "hot_value": 2210000,
            "platform": "weibo",
            "category": "效率",
            "summary": "从智能知识库到自动化剪辑与代码生成，高阶效率玩家的武器库大盘点。",
            "url": "https://s.weibo.com/weibo?q=AI效率工具"
        },
        {
            "title": "长文本推理与认知记忆架构突破",
            "hot_value": 1850000,
            "platform": "weibo",
            "category": "AI",
            "summary": "学术界与产业界最新论文聚焦无限上下文下的认知留存与动态进化机制。",
            "url": "https://s.weibo.com/weibo?q=认知记忆"
        }
    ],
    "zhihu": [
        {
            "title": "如何看待2026年AI智能体全面爆发对商业模式的重塑？",
            "hot_value": 8900000,
            "platform": "zhihu",
            "category": "商业",
            "summary": "讨论各行业从单点工具向自主协同智能体演进带来的结构性重塑机遇与商业壁垒迁移。",
            "url": "https://www.zhihu.com/question/100001"
        },
        {
            "title": "有哪些真正能够提升个人工作效率10倍的思维框架与工具？",
            "hot_value": 6720000,
            "platform": "zhihu",
            "category": "效率",
            "summary": "深度拆解高段位从业者的思维模型、自动化工作流与认知资产沉淀方法。",
            "url": "https://www.zhihu.com/question/100002"
        },
        {
            "title": "独立开发者出海如何构建可持续的现金流业务？",
            "hot_value": 5430000,
            "platform": "zhihu",
            "category": "独立开发",
            "summary": "从选品策略、Landing Page转化到冷启动与Stripe订阅全链路实战经验分享。",
            "url": "https://www.zhihu.com/question/100003"
        },
        {
            "title": "大语言模型认知架构的本质演进路径是什么？",
            "hot_value": 4890000,
            "platform": "zhihu",
            "category": "AI",
            "summary": "探讨从提示词工程到动态自我迭代、思考链路追踪与价值观对齐的深层逻辑。",
            "url": "https://www.zhihu.com/question/100004"
        },
        {
            "title": "普通人如何在智能化浪潮中建立自己的认知IP与个人护城河？",
            "hot_value": 3980000,
            "platform": "zhihu",
            "category": "商业",
            "summary": "知识不再是门槛，独特的审美品味、价值观表达与思考DNA才是核心壁垒。",
            "url": "https://www.zhihu.com/question/100005"
        }
    ],
    "bilibili": [
        {
            "title": "【硬核】从零搭建属于你的个人认知智能体！",
            "hot_value": 3200000,
            "platform": "bilibili",
            "category": "AI",
            "summary": "保姆级教程：手把手教你打造带长期记忆与认知进化的专属工作流助手。",
            "url": "https://www.bilibili.com/video/BV100001"
        },
        {
            "title": "独立开发一人成军：2026年全栈效率工具栈实操指南",
            "hot_value": 2450000,
            "platform": "bilibili",
            "category": "独立开发",
            "summary": "一人全包设计、后端、部署与营销，全流程自动化实战拆解。",
            "url": "https://www.bilibili.com/video/BV100002"
        },
        {
            "title": "AI时代的商业变现与思维破局：普通人如何抓住智能红利？",
            "hot_value": 1980000,
            "platform": "bilibili",
            "category": "商业",
            "summary": "深入剖析商业本质，告别单纯卖课信息差，构建高粘性服务型产品。",
            "url": "https://www.bilibili.com/video/BV100003"
        },
        {
            "title": "别再死记硬背！用认知卡片与深度链接构建第二大脑",
            "hot_value": 1650000,
            "platform": "bilibili",
            "category": "效率",
            "summary": "高阶知识管理工作流演示，将碎片信息自动化转化为结构化资产。",
            "url": "https://www.bilibili.com/video/BV100004"
        },
        {
            "title": "开源大模型本地部署与微调全流程测评",
            "hot_value": 1420000,
            "platform": "bilibili",
            "category": "AI",
            "summary": "多卡环境实测不同开源底座的吞吐性能与微调显存占用表现。",
            "url": "https://www.bilibili.com/video/BV100005"
        }
    ],
    "36kr": [
        {
            "title": "36氪独家｜AI Agent爆发元年：企业效率革命与商业重塑新图景",
            "hot_value": 4500000,
            "platform": "36kr",
            "category": "AI",
            "summary": "数十家头部企业披露智能体落地实操案例，人机协同率提升超过60%。",
            "url": "https://36kr.com/p/200001"
        },
        {
            "title": "出海观察：独立开发者的第二增长曲线在哪里？",
            "hot_value": 3100000,
            "platform": "36kr",
            "category": "独立开发",
            "summary": "微型SaaS在欧美市场的获客成本与LTV测算，垂直赛道仍有巨大红利。",
            "url": "https://36kr.com/p/200002"
        },
        {
            "title": "效率革命：下一代企业知识库系统如何实现认知闭环",
            "hot_value": 2600000,
            "platform": "36kr",
            "category": "效率",
            "summary": "传统知识管理沉睡不醒，基于思考DNA与自动化比对的新型系统受资方青睐。",
            "url": "https://36kr.com/p/200003"
        },
        {
            "title": "2026新商业格局：从规模经济转向超级个体网络",
            "hot_value": 2150000,
            "platform": "36kr",
            "category": "商业",
            "summary": "分布式组织形态兴起，小团队依靠算力与智能体放大商业杠杆。",
            "url": "https://36kr.com/p/200004"
        },
        {
            "title": "硬件巨头纷纷下场，端侧大模型重塑个人计算终端体验",
            "hot_value": 1890000,
            "platform": "36kr",
            "category": "AI",
            "summary": "算力芯片迭代驱动端云协同，低延迟离线智能成为最新竞争焦点。",
            "url": "https://36kr.com/p/200005"
        }
    ],
    "douyin": [
        {
            "title": "一人公司时代来了！独立开发AI神器分享",
            "hot_value": 5800000,
            "platform": "douyin",
            "category": "独立开发",
            "summary": "普通人也能独立做出出海爆款，这几个自动化工具赶紧收藏起来！",
            "url": "https://www.douyin.com/video/100001"
        },
        {
            "title": "真正提升10倍工作效率的AI黑科技实操",
            "hot_value": 4920000,
            "platform": "douyin",
            "category": "效率",
            "summary": "告别无意义加班！掌握这套智能体提示工程，工作半小时搞定。",
            "url": "https://www.douyin.com/video/100002"
        },
        {
            "title": "2026商业认知与财富思维：普通人的翻盘机会",
            "hot_value": 4310000,
            "platform": "douyin",
            "category": "商业",
            "summary": "拉开人与人差距的从来不是勤奋程度，而是对新生产力工具的敏锐度。",
            "url": "https://www.douyin.com/video/100003"
        },
        {
            "title": "大模型让内容创作变天了！认知IP打造核心秘诀",
            "hot_value": 3670000,
            "platform": "douyin",
            "category": "AI",
            "summary": "为什么千篇一律的AI文章没人看？因为缺少了独特的思考DNA与骨架。",
            "url": "https://www.douyin.com/video/100004"
        },
        {
            "title": "打工人必备！高效认知输入与输出工作法",
            "hot_value": 2890000,
            "platform": "douyin",
            "category": "效率",
            "summary": "如何像海绵一样吸收高价值知识，并用结构化框架快速变现。",
            "url": "https://www.douyin.com/video/100005"
        }
    ]
}

