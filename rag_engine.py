# -*- coding: utf-8 -*-
import os
import re
import csv
import json
import sqlite3
import math
import io
import time
import requests
from datetime import datetime
from collections import Counter

# 预设高频技术实体字典
TECH_SKILL_LEXICON = {
    # AI / LLM / Agent
    "agent", "ai agent", "智能体", "rag", "langchain", "llamaindex", "dify", "fastgpt", "coze", "flowise",
    "prompt", "提示词", "llm", "大模型", "gpt", "claude", "gemini", "deepseek", "chatgpt", "transformer",
    "fine-tune", "微调", "lora", "sft", "rlhf", "embedding", "向量", "知识库", "知识图谱", "rerank",
    "nlp", "自然语言处理", "cv", "计算机视觉", "multimodal", "多模态", "aigc", "stable diffusion", "midjourney",
    "comfyui", "diffusion", "sora", "tts", "asr", "语音识别", "人脸识别",
    # 编程语言与框架
    "python", "pytorch", "tensorflow", "keras", "scikit-learn", "numpy", "pandas",
    "fastapi", "flask", "django", "vue", "react", "typescript", "javascript", "html", "css",
    "java", "spring", "c++", "c#", "golang", "go", "rust", "sql", "mysql", "postgresql",
    "redis", "mongodb", "elasticsearch", "docker", "k8s", "kubernetes", "linux", "git",
    "crawling", "爬虫", "drissionpage", "selenium", "playwright", "scrapy", "automation", "自动化"
}

# 预设内置四大黑名单矩阵库
DEFAULT_OUTSOURCING_COMPANIES = [
    "中软国际", "软通动力", "法本信息", "文思海辉", "润和软件", "柯莱特", "博彦科技", "诚迈科技",
    "拓保软件", "瞬联科技", "易宝软件", "赛意信息", "宇信科技", "赞同科技", "神州数码", "东软集团",
    "软讯科技", "亚信科技", "纬创软件", "银雁科技", "艾融软件", "亿达信息", "中电金信", "南京烽火",
    "恒生电子驻场", "中科创达外包", "佰钧成", "新致软件", "信必优", "微创软件", "信雅达", "大宇宙",
    "信华信", "九桥科技", "软帝联合", "安硕信息", "科蓝软件", "同花顺外派", "京北方", "迈格信息",
    "青软青之", "天阳科技", "赢时胜", "北明软件", "南天信息", "润联科技", "联合永道", "海量数据外派"
]

DEFAULT_TRAINING_AGENCIES = [
    "达内", "传智", "千锋", "黑马程序员", "火星时代", "优就业", "尚硅谷", "实训生", "招转培",
    "就业实训", "产学研基地", "零基础包学会", "岗前培训", "免费培训", "包就业", "就业协议", "实训基地",
    "青软实训", "华清远见", "兄弟连", "中公优就业", "课工场", "北大青鸟", "源码时代", "硅谷动力",
    "蜗牛学院", "动力节点", "育知同创", "软帝科技培训", "实训生定向", "助学贷款培训"
]

DEFAULT_SCAM_CATEGORIES = [
    "短剧", "AI漫剧", "小说推文", "声音主播", "游戏代练", "打字员", "挂机", "抖音图文",
    "影视剪辑", "课程顾问", "话务员", "电话销售", "地推", "兼职打标", "分镜师", "二次创意",
    "买手", "刷单", "兼职模特", "电竞选手", "小说录音", "语音陪聊", "点赞员", "手工兼职"
]

DEFAULT_JD_BODY_EXCLUDES = [
    "长期全国出差", "接受全国驻场外派", "统招博士", "全日制博士", "统招985/211研究生", "必须5年以上架构经验",
    "必须10年以上相关经验", "需缴纳押金", "入职需购买设备", "自带电脑办公无补贴", "招转培", "岗前实训三个月"
]


class RagEngine:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._matrix_cache = None
        self._matrix_cache_time = 0.0
        self._profile_cache = None
        self._profile_cache_time = 0.0
        self._init_db()

    def invalidate_cache(self):
        """清除内存热点缓存"""
        self._matrix_cache = None
        self._matrix_cache_time = 0.0
        self._profile_cache = None
        self._profile_cache_time = 0.0

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            # 1. 简历画像表
            conn.execute("""
            CREATE TABLE IF NOT EXISTS resume_profile (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT DEFAULT '',
                raw_text TEXT NOT NULL,
                target_titles TEXT DEFAULT '[]',
                tech_skills TEXT DEFAULT '[]',
                education TEXT DEFAULT '',
                experience_years REAL DEFAULT 0,
                summary TEXT DEFAULT '',
                updated_at TEXT NOT NULL
            );
            """)

            # 2. 简历 RAG 知识切片库
            conn.execute("""
            CREATE TABLE IF NOT EXISTS resume_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section_name TEXT NOT NULL,
                chunk_text TEXT NOT NULL,
                tech_tags TEXT DEFAULT '[]',
                created_at TEXT NOT NULL
            );
            """)

            # 3. 学习出的岗位偏好模型
            conn.execute("""
            CREATE TABLE IF NOT EXISTS learned_profile (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                positive_keywords TEXT DEFAULT '[]',
                negative_keywords TEXT DEFAULT '[]',
                top_skills TEXT DEFAULT '[]',
                preferred_titles TEXT DEFAULT '[]',
                salary_bracket TEXT DEFAULT '',
                salary_stats TEXT DEFAULT '{}',
                company_types TEXT DEFAULT '[]',
                recommended_search_keywords TEXT DEFAULT '',
                min_match_score INTEGER DEFAULT 65,
                enable_rag_filter INTEGER DEFAULT 1,
                total_analyzed_jobs INTEGER DEFAULT 0,
                updated_at TEXT NOT NULL
            );
            """)

            # 4. 分层黑名单过滤矩阵
            conn.execute("""
            CREATE TABLE IF NOT EXISTS filter_matrix (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                item_name TEXT NOT NULL UNIQUE,
                is_enabled INTEGER DEFAULT 1,
                created_at TEXT NOT NULL
            );
            """)

            # 5. 全渠道投递岗位知识库 (含自动打招呼与手动投递，结构化入库)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS delivered_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company TEXT NOT NULL,
                title TEXT NOT NULL,
                salary TEXT DEFAULT '',
                job_url TEXT DEFAULT '',
                job_id TEXT DEFAULT '',
                boss_id TEXT DEFAULT '',
                source TEXT DEFAULT 'manual',
                jd_text TEXT DEFAULT '',
                delivered_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_delivered_company_title ON delivered_jobs (company, title);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_delivered_job_id ON delivered_jobs (job_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_delivered_boss_id ON delivered_jobs (boss_id);")

            # 6. 用户人机偏好对齐训练样本库 (持久化存储用户在模拟岗位上的每一次判定，增量累加)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS user_job_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                salary TEXT DEFAULT '',
                decision TEXT NOT NULL,
                reasons TEXT DEFAULT '[]',
                company_type TEXT DEFAULT '',
                category_tag TEXT DEFAULT '',
                created_at TEXT NOT NULL
            );
            """)

            # 7. AI 偏好自然语言对话记忆库 (用户针对被过滤岗位的纠偏与意图记忆)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS ai_chat_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                memory_tags TEXT DEFAULT '[]',
                created_at TEXT NOT NULL
            );
            """)

            # 检查字段兼容性迁移 (旧表结构升级)
            try:
                conn.execute("ALTER TABLE learned_profile ADD COLUMN salary_stats TEXT DEFAULT '{}'")
            except Exception: pass
            try:
                conn.execute("ALTER TABLE learned_profile ADD COLUMN company_types TEXT DEFAULT '[]'")
            except Exception: pass
            try:
                conn.execute("ALTER TABLE learned_profile ADD COLUMN recommended_search_keywords TEXT DEFAULT ''")
            except Exception: pass

            # 初始化内置黑名单
            count = conn.execute("SELECT COUNT(*) as cnt FROM filter_matrix").fetchone()["cnt"]
            if count == 0:
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                for c in DEFAULT_OUTSOURCING_COMPANIES:
                    conn.execute("INSERT OR IGNORE INTO filter_matrix (category, item_name, is_enabled, created_at) VALUES ('outsourcing', ?, 1, ?)", (c, now_str))
                for c in DEFAULT_TRAINING_AGENCIES:
                    conn.execute("INSERT OR IGNORE INTO filter_matrix (category, item_name, is_enabled, created_at) VALUES ('training', ?, 1, ?)", (c, now_str))
                for c in DEFAULT_SCAM_CATEGORIES:
                    conn.execute("INSERT OR IGNORE INTO filter_matrix (category, item_name, is_enabled, created_at) VALUES ('scam', ?, 1, ?)", (c, now_str))
                for c in DEFAULT_JD_BODY_EXCLUDES:
                    conn.execute("INSERT OR IGNORE INTO filter_matrix (category, item_name, is_enabled, created_at) VALUES ('jd_body_exclude', ?, 1, ?)", (c, now_str))

            # 初始化默认偏好模型
            row = conn.execute("SELECT id FROM learned_profile WHERE id = 1").fetchone()
            if not row:
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                conn.execute("""
                INSERT INTO learned_profile (id, positive_keywords, negative_keywords, top_skills, preferred_titles, min_match_score, enable_rag_filter, total_analyzed_jobs, updated_at)
                VALUES (1, '["AI Agent", "大模型应用", "Python", "智能体", "Prompt"]', '["销售", "电话销售", "主播"]', '["Python", "Agent", "FastAPI", "RAG"]', '["AI工程师", "Agent开发"]', 65, 1, 0, ?)
                """, (now_str,))
            conn.commit()

    # ============================
    # 简历文件提取与切片
    # ============================
    @staticmethod
    def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
        """从上传的 PDF / Word / TXT / MD 文件中提取文本正文"""
        name_lower = filename.lower()
        if name_lower.endswith(".pdf"):
            try:
                import pypdf
                reader = pypdf.PdfReader(io.BytesIO(file_bytes))
                texts = []
                for p in reader.pages:
                    txt = p.extract_text()
                    if txt: texts.append(txt)
                return "\n".join(texts).strip()
            except Exception as e:
                raise ValueError(f"解析 PDF 简历失败: {e}")

        elif name_lower.endswith(".docx"):
            try:
                import docx
                doc = docx.Document(io.BytesIO(file_bytes))
                return "\n".join([p.text for p in doc.paragraphs if p.text.strip()]).strip()
            except Exception as e:
                raise ValueError(f"解析 Word 简历失败: {e}")

        else:
            # 文本类型 UTF-8 / GBK / GB18030 尝试
            for enc in ["utf-8", "gb18030", "gbk", "utf-16"]:
                try:
                    return file_bytes.decode(enc).strip()
                except Exception:
                    continue
            return file_bytes.decode("utf-8", errors="ignore").strip()

    def parse_and_save_resume(self, raw_text: str, filename: str = "简历.txt") -> dict:
        """
        深度解析简历正文：
        1. 自动抽取技术栈技能 (对照高频实体字典)
        2. 自动抽取学历与工作经验年限
        3. 自动抽取意向岗位方向
        4. 语义切片保存至 resume_chunks RAG 知识库
        """
        if not raw_text or len(raw_text.strip()) < 10:
            raise ValueError("简历正文内容过短或为空")

        text_lower = raw_text.lower()

        # 1. 抽取技术技能
        found_skills = set()
        for skill in TECH_SKILL_LEXICON:
            if re.match(r'^[a-z0-9\+\#\.]+$', skill):
                pattern = r'(?<![a-z0-9])' + re.escape(skill) + r'(?![a-z0-9])'
                if re.search(pattern, text_lower):
                    found_skills.add(skill.upper() if len(skill) <= 3 else skill.capitalize())
            else:
                if skill in text_lower:
                    found_skills.add(skill)

        # 2. 抽取学历 (按最高学历优先判定，避免专升本/本科在读被错误覆盖为大专)
        edu = "本科"
        if "博士" in raw_text:
            edu = "博士"
        elif "硕士" in raw_text or "研究生" in raw_text:
            edu = "硕士"
        elif "本科" in raw_text or "大学" in raw_text or "学士" in raw_text:
            edu = "本科"
        elif "大专" in raw_text or "专科" in raw_text:
            edu = "大专"

        # 3. 抽取经验年限
        exp_years = 1.0
        exp_match = re.search(r'(\d+)\s*年\s*(?:工作|开发|实战|项目)?经验', raw_text)
        if exp_match:
            try:
                exp_years = float(exp_match.group(1))
            except Exception:
                pass
        elif "应届" in raw_text or "在校" in raw_text or "实习" in raw_text or "2027" in raw_text or "27届" in raw_text:
            exp_years = 0.5

        # 4. 抽取意向岗位词
        target_titles = []
        for kw in ["AI大模型应用开发", "AI应用工程师", "AI Agent工程师", "大模型应用开发", "大模型工程师", "AI应用", "Agent开发", "Python工程师", "智能体开发", "算法工程师", "后端工程师", "自动化工程师"]:
            if kw.lower() in text_lower:
                target_titles.append(kw)
        if not target_titles:
            target_titles = ["AI Agent开发", "大模型应用开发", "Python工程师"]

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        profile = {
            "filename": filename,
            "raw_text": raw_text[:4000],
            "target_titles": target_titles,
            "tech_skills": sorted(list(found_skills)),
            "education": edu,
            "experience_years": exp_years,
            "summary": f"{edu}学历 | {exp_years}年实战经验 | 核心技能: {', '.join(sorted(list(found_skills))[:8])}",
            "updated_at": now_str
        }

        # 5. 智能分块切片并持久化到 RAG 向量切片库
        # 寻找常见章节分割点
        section_headers = [
            ("专业技能", r'(?:专业技能|技术特长|核心技能|个人技能|掌握技能)'),
            ("项目经历", r'(?:项目经验|项目经历|实战项目|代表项目)'),
            ("工作经历", r'(?:工作经历|工作经验|实习经历|职业履历)'),
            ("教育背景", r'(?:教育经历|教育背景|毕业院校)'),
            ("自我评价", r'(?:自我评价|个人总结|个人优势|关于我)')
        ]

        chunks = []
        lines = raw_text.splitlines()
        current_sec = "简历概况"
        current_lines = []

        for line in lines:
            line_s = line.strip()
            if not line_s: continue
            matched_header = None
            for h_name, h_pattern in section_headers:
                if re.match(r'^[#\*\s-]*' + h_pattern, line_s):
                    matched_header = h_name
                    break
            if matched_header:
                if current_lines:
                    chunk_t = "\n".join(current_lines).strip()
                    if chunk_t:
                        sec_tags = [s for s in profile["tech_skills"] if s.lower() in chunk_t.lower()]
                        chunks.append((current_sec, chunk_t, json.dumps(sec_tags, ensure_ascii=False)))
                    current_lines = []
                current_sec = matched_header
            else:
                current_lines.append(line_s)

        if current_lines:
            chunk_t = "\n".join(current_lines).strip()
            if chunk_t:
                sec_tags = [s for s in profile["tech_skills"] if s.lower() in chunk_t.lower()]
                chunks.append((current_sec, chunk_t, json.dumps(sec_tags, ensure_ascii=False)))

        # 若未成功按标题切出多个，兜底按长度切块
        if len(chunks) <= 1:
            chunks = []
            chunk_size = 400
            for i in range(0, len(raw_text), chunk_size):
                sub = raw_text[i:i+chunk_size].strip()
                if sub:
                    sec_tags = [s for s in profile["tech_skills"] if s.lower() in sub.lower()]
                    chunks.append((f"简历知识块-{len(chunks)+1}", sub, json.dumps(sec_tags, ensure_ascii=False)))

        with self._get_conn() as conn:
            conn.execute("DELETE FROM resume_profile")
            conn.execute("""
            INSERT INTO resume_profile (filename, raw_text, target_titles, tech_skills, education, experience_years, summary, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                filename,
                raw_text,
                json.dumps(target_titles, ensure_ascii=False),
                json.dumps(profile["tech_skills"], ensure_ascii=False),
                edu,
                exp_years,
                profile["summary"],
                now_str
            ))

            conn.execute("DELETE FROM resume_chunks")
            for sec_name, c_text, tags_json in chunks:
                conn.execute("""
                INSERT INTO resume_chunks (section_name, chunk_text, tech_tags, created_at)
                VALUES (?, ?, ?, ?)
                """, (sec_name, c_text, tags_json, now_str))

            conn.commit()

        return profile

    def get_resume_profile(self) -> dict:
        """获取当前系统已解析的简历结构化数据"""
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM resume_profile ORDER BY id DESC LIMIT 1").fetchone()
            if not row:
                return {}
            return {
                "id": row["id"],
                "filename": row["filename"],
                "raw_text": row["raw_text"],
                "target_titles": json.loads(row["target_titles"] or '[]'),
                "tech_skills": json.loads(row["tech_skills"] or '[]'),
                "education": row["education"],
                "experience_years": row["experience_years"],
                "summary": row["summary"],
                "updated_at": row["updated_at"]
            }

    def get_resume_chunks(self) -> list[dict]:
        """获取当前入库的全部 RAG 简历知识切片"""
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM resume_chunks ORDER BY id ASC").fetchall()
            return [
                {
                    "id": r["id"],
                    "section_name": r["section_name"],
                    "chunk_text": r["chunk_text"],
                    "tech_tags": json.loads(r["tech_tags"] or '[]'),
                    "created_at": r["created_at"]
                }
                for r in rows
            ]

    def clear_resume(self) -> bool:
        """清空/删除当前已入库的简历画像及其所有 RAG 知识切片，并清除缓存"""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM resume_profile")
            conn.execute("DELETE FROM resume_chunks")
            conn.commit()
        self.invalidate_cache()
        return True

    def delete_resume_document(self, filename: str) -> bool:
        """从知识库及本地数据存储中彻底删除指定的简历或资料文件与对应切片"""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM resume_profile WHERE filename = ?", (filename,))
            count = conn.execute("SELECT count(*) FROM resume_profile").fetchone()[0]
            if count == 0:
                conn.execute("DELETE FROM resume_chunks")
            conn.commit()
        self.invalidate_cache()

        # 清理 data/ 目录下对应的物理文件
        data_dir = os.path.dirname(os.path.abspath(self.db_path))
        target_f = os.path.join(data_dir, filename)
        if os.path.exists(target_f):
            try:
                os.remove(target_f)
            except Exception as e:
                print(f"[Warn] 删除磁盘文件失败: {e}")
        return True

    def list_knowledge_documents(self) -> list:
        """获取所有已入库的简历/资料清单（包含当前生效画像与数据目录文件）"""
        docs = []
        data_dir = os.path.dirname(os.path.abspath(self.db_path))

        # 1. 数据库中已入库的简历画像
        prof = self.get_resume_profile()
        chunks = self.get_resume_chunks()
        active_filename = prof.get("filename") if prof else None

        if prof and prof.get("raw_text"):
            docs.append({
                "filename": prof.get("filename", "未命名简历"),
                "status": "已入库生效",
                "chunks_count": len(chunks),
                "skills_count": len(prof.get("tech_skills", [])),
                "updated_at": prof.get("updated_at", ""),
                "is_active": True
            })

        # 2. 扫描 data/ 目录下的其他简历或资料文件
        if os.path.exists(data_dir):
            for f in os.listdir(data_dir):
                if f.lower().endswith(('.pdf', '.docx', '.txt', '.md')):
                    if active_filename and f == active_filename:
                        continue
                    f_path = os.path.join(data_dir, f)
                    try:
                        mtime = datetime.fromtimestamp(os.path.getmtime(f_path)).strftime("%Y-%m-%d %H:%M:%S")
                        f_size = round(os.path.getsize(f_path) / 1024, 1)
                        docs.append({
                            "filename": f,
                            "status": "本地文件",
                            "chunks_count": 0,
                            "skills_count": 0,
                            "updated_at": mtime,
                            "file_size_kb": f_size,
                            "is_active": False
                        })
                    except Exception:
                        pass
        return docs

    # ============================
    # 历史投递自动深度学习
    # ============================
    def auto_learn_from_history(self, history_csv_path: str) -> dict:
        """
        深度解析 history.csv 中所有已投递岗位作为正向正样本：
        1. 自动聚类高频岗位特征与词频分布
        2. 自动统计偏好薪资区间 (月薪分布 vs 日薪分布)
        3. 自动聚类偏好企业行业特征
        4. 提取与简历技术交集并生成推荐搜索词
        """
        if not os.path.exists(history_csv_path):
            return {"success": False, "message": f"未找到投递历史文件: {history_csv_path}"}

        companies = []
        titles = []
        salaries = []

        try:
            with open(history_csv_path, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                for row in reader:
                    if row and len(row) >= 4:
                        c = row[1].strip()
                        t = row[2].strip()
                        s = row[3].strip()
                        if c: companies.append(c)
                        if t: titles.append(t)
                        if s: salaries.append(s)
        except Exception as e:
            return {"success": False, "message": f"读取投递历史异常: {e}"}

        total_count = len(titles)
        if total_count == 0:
            return {"success": False, "message": "历史记录中暂无数据"}

        # 1. 词频与短语提炼 (从岗位标题中提取关键词)
        token_counter = Counter()
        for t in titles:
            clean_t = re.sub(r'[\(\)（）\-\+\/·]+', ' ', t)
            words = clean_t.split()
            for w in words:
                w_str = w.strip()
                if len(w_str) >= 2 and not w_str.isdigit():
                    token_counter[w_str] += 1
            for key in ["AI Agent", "Agent", "AI工程师", "大模型", "Python", "人工智能", "算法", "NLP", "全栈", "自动化"]:
                if key.lower() in t.lower():
                    token_counter[key] += 3

        top_positive_words = [item[0] for item in token_counter.most_common(15)]

        # 2. 统计高频岗位标题
        title_counter = Counter(titles)
        top_preferred_titles = [item[0] for item in title_counter.most_common(6)]

        # 3. 统计薪资特征 (区分 月薪 K 与 日薪 元/天)
        month_salaries = []
        day_salaries = []
        for s in salaries:
            # 日薪：150-200元/天
            m_day = re.search(r'(\d+)\s*-\s*(\d+)\s*元/天', s)
            if m_day:
                day_salaries.append((int(m_day.group(1)) + int(m_day.group(2))) / 2)
                continue
            # 月薪：7-12K
            m_month = re.search(r'(\d+)\s*-\s*(\d+)\s*K', s, re.I)
            if m_month:
                month_salaries.append((int(m_month.group(1)) + int(m_month.group(2))) / 2)

        salary_desc = ""
        salary_stats = {}
        if month_salaries:
            avg_m = int(sum(month_salaries) / len(month_salaries))
            min_m = int(min(month_salaries))
            max_m = int(max(month_salaries))
            salary_desc += f"{min_m}-{max_m}K (均值 {avg_m}K)"
            salary_stats["month"] = {"min": min_m, "max": max_m, "avg": avg_m}

        if day_salaries:
            avg_d = int(sum(day_salaries) / len(day_salaries))
            min_d = int(min(day_salaries))
            max_d = int(max(day_salaries))
            day_str = f"{min_d}-{max_d}元/天 (均值 {avg_d}元/天)"
            salary_desc = f"{salary_desc} | {day_str}" if salary_desc else day_str
            salary_stats["day"] = {"min": min_d, "max": max_d, "avg": avg_d}

        if not salary_desc:
            salary_desc = "面议 / 灵活薪资区间"

        # 4. 企业类型特征提炼
        comp_types_counter = Counter()
        for c in companies:
            for kw in ["科技", "网络", "软件", "智能", "电子商务", "文化传媒", "实业", "国际", "医疗", "金融"]:
                if kw in c:
                    comp_types_counter[kw] += 1
        top_comp_types = [item[0] for item in comp_types_counter.most_common(5)]

        # 5. 结合简历画像提取技能交集
        resume = self.get_resume_profile()
        resume_skills = set(s.lower() for s in resume.get("tech_skills", []))

        learned_skills = []
        for item, _ in token_counter.most_common(40):
            if item.lower() in resume_skills or any(item.lower() == s for s in TECH_SKILL_LEXICON):
                learned_skills.append(item)

        # 推荐搜索关键词组合
        rec_kws = []
        for w in ["AI Agent", "大模型", "Python", "AI应用", "智能体", "自动化"]:
            if w in top_positive_words or w.lower() in [s.lower() for s in top_preferred_titles]:
                if w not in rec_kws:
                    rec_kws.append(w)
        if not rec_kws:
            rec_kws = top_positive_words[:4]

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        res_data = {
            "total_analyzed_jobs": total_count,
            "positive_keywords": top_positive_words[:12],
            "top_skills": list(dict.fromkeys(learned_skills))[:10] or ["Python", "AI Agent", "大模型", "FastAPI"],
            "preferred_titles": top_preferred_titles or ["AI Agent工程师", "大模型应用开发"],
            "salary_bracket": salary_desc,
            "salary_stats": salary_stats,
            "company_types": top_comp_types,
            "recommended_search_keywords": ", ".join(rec_kws[:4]),
            "updated_at": now_str
        }

        with self._get_conn() as conn:
            conn.execute("""
            UPDATE learned_profile SET
                positive_keywords = ?,
                top_skills = ?,
                preferred_titles = ?,
                salary_bracket = ?,
                salary_stats = ?,
                company_types = ?,
                recommended_search_keywords = ?,
                total_analyzed_jobs = ?,
                updated_at = ?
            WHERE id = 1
            """, (
                json.dumps(res_data["positive_keywords"], ensure_ascii=False),
                json.dumps(res_data["top_skills"], ensure_ascii=False),
                json.dumps(res_data["preferred_titles"], ensure_ascii=False),
                res_data["salary_bracket"],
                json.dumps(salary_stats, ensure_ascii=False),
                json.dumps(res_data["company_types"], ensure_ascii=False),
                res_data["recommended_search_keywords"],
                total_count,
                now_str
            ))
            conn.commit()

        return {"success": True, "data": res_data}

    def get_learned_profile(self) -> dict:
        """获取当前已习得的求职偏好画像模型"""
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM learned_profile WHERE id = 1").fetchone()
            if not row:
                return {}
            return {
                "id": row["id"],
                "positive_keywords": json.loads(row["positive_keywords"] or '[]'),
                "negative_keywords": json.loads(row["negative_keywords"] or '[]'),
                "top_skills": json.loads(row["top_skills"] or '[]'),
                "preferred_titles": json.loads(row["preferred_titles"] or '[]'),
                "salary_bracket": row["salary_bracket"] or "未统计",
                "salary_stats": json.loads(row["salary_stats"] or '{}'),
                "company_types": json.loads(row["company_types"] or '[]'),
                "recommended_search_keywords": row["recommended_search_keywords"] or "AI Agent, 大模型, Python",
                "min_match_score": row["min_match_score"] or 65,
                "enable_rag_filter": bool(row["enable_rag_filter"]),
                "total_analyzed_jobs": row["total_analyzed_jobs"] or 0,
                "updated_at": row["updated_at"]
            }

    # ============================
    # 第二层：RAG 智能精选契合度打分器
    # ============================
    def calculate_match_score(self, job_title: str, company: str, salary: str, jd_text: str = "") -> dict:
        """
        基于本地 RAG 知识库与投递偏好画像，计算岗位综合精选契合度得分 (0-100分)
        多维度综合评价：
        1. 简历核心技能覆盖度 (满分 40分)
        2. 职位标题与业务方向对齐度 (满分 30分)
        3. 历史投递偏好与正向特征契合度 (满分 20分)
        4. 学历经验与薪资合理度基线分 (满分 10分)
        """
        # 内存热点缓存：避免高频投递循环中每个岗位都进行两次 SQLite 磁盘 I/O
        now = time.time()
        if self._profile_cache is None or (now - self._profile_cache_time) > 10.0:
            with self._get_conn() as conn:
                model_row = conn.execute("SELECT * FROM learned_profile WHERE id = 1").fetchone()
                resume_row = conn.execute("SELECT * FROM resume_profile ORDER BY id DESC LIMIT 1").fetchone()
                self._profile_cache = (model_row, resume_row)
                self._profile_cache_time = now
        else:
            model_row, resume_row = self._profile_cache

        min_score = model_row["min_match_score"] if model_row else 65
        enable_rag = bool(model_row["enable_rag_filter"]) if model_row else True

        if not resume_row:
            # 未上传简历时默认全通过
            return {
                "pass": True,
                "score": 80,
                "min_score": min_score,
                "reason": "未上传简历，跳过第二层精选评分",
                "matched_skills": [],
                "missing_skills": [],
                "skill_score": 35,
                "title_score": 25,
                "pref_score": 15,
                "base_score": 5
            }

        resume_skills = set(json.loads(resume_row["tech_skills"] or '[]'))
        target_titles = json.loads(resume_row["target_titles"] or '[]')
        full_jd = f"{job_title} {company} {jd_text}".lower()

        # 1. 技能匹配得分 (满分 40 分)
        matched_skills = []
        for s in resume_skills:
            if s.lower() in full_jd:
                matched_skills.append(s)

        if resume_skills:
            skill_coverage = len(matched_skills) / len(resume_skills)
            skill_score = min(40, int(skill_coverage * 55))
        else:
            skill_score = 25

        # 2. 职位标题相关度得分 (满分 30 分)
        title_score = 0
        t_lower = job_title.lower()
        for tt in target_titles:
            if tt.lower() in t_lower or any(w.lower() in t_lower for w in tt.split()):
                title_score = 30
                break
        if title_score == 0:
            for kw in ["ai", "agent", "python", "智能体", "大模型", "算法", "全栈", "自动化"]:
                if kw in t_lower:
                    title_score = 22
                    break
        if title_score == 0:
            title_score = 10

        # 3. 历史投递偏好契合度 (满分 20 分)
        pref_score = 12
        matched_pos_words = []
        if model_row:
            pos_kws = json.loads(model_row["positive_keywords"] or '[]')
            for pk in pos_kws:
                if pk.lower() in full_jd:
                    matched_pos_words.append(pk)
            pref_score = min(20, 8 + len(matched_pos_words) * 3)

        # 4. 学历经验与薪资基线分 (满分 10 分)
        base_score = 10
        # 如果 JD 中含有硬性无法达到的要求则扣分
        if "统招博士" in jd_text or "全日制博士" in jd_text:
            base_score = 2
        elif "10年以上" in jd_text or "8年以上" in jd_text:
            base_score = 4

        total_score = min(100, skill_score + title_score + pref_score + base_score)

        is_passed = True
        reject_reason = ""
        missing_skills = [s for s in list(resume_skills)[:6] if s not in matched_skills]

        if enable_rag and total_score < min_score:
            is_passed = False
            reject_reason = f"🎯 [AI精选未达标] 综合契合度仅 {total_score}分 (低于精选门槛 {min_score}分)"
            if missing_skills:
                reject_reason += f" | 缺少核心技术栈: {', '.join(missing_skills[:3])}"

        return {
            "pass": is_passed,
            "score": total_score,
            "min_score": min_score,
            "enable_rag": enable_rag,
            "reason": reject_reason if not is_passed else f"🌟 [AI精选推荐: {total_score}分]",
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "matched_pos_words": matched_pos_words,
            "skill_score": skill_score,
            "title_score": title_score,
            "pref_score": pref_score,
            "base_score": base_score
        }

    # ============================
    # 四重分层智能黑名单过滤矩阵
    # ============================
    def check_blacklist_matrix(self, company: str, job_title: str, jd_text: str = "") -> tuple[bool, str]:
        """
        四重黑名单极速拦截：
        1. 外包公司库
        2. 培训与招生套路库
        3. 擦边引流行业库
        4. JD 详情正文硬性排除规则
        返回: (is_blocked: bool, block_reason: str)
        """
        # 内存热点缓存：避免高频循环中每次卡片和 JD 判断都读库
        now = time.time()
        if self._matrix_cache is None or (now - self._matrix_cache_time) > 10.0:
            with self._get_conn() as conn:
                self._matrix_cache = conn.execute("SELECT category, item_name FROM filter_matrix WHERE is_enabled = 1").fetchall()
                self._matrix_cache_time = now
        rows = self._matrix_cache

        c_lower = company.lower()
        t_lower = job_title.lower()
        jd_lower = jd_text.lower() if jd_text else ""

        for r in rows:
            cat = r["category"]
            item = r["item_name"].strip()
            item_lower = item.lower()

            # 1. 公司黑名单 (外包 + 培训)
            if cat in ("outsourcing", "training"):
                if item_lower in c_lower:
                    cat_name = "外包公司" if cat == "outsourcing" else "培训招生机构"
                    return True, f"命中{cat_name}黑名单: 【{item}】"

            # 2. 岗位擦边/黑产黑名单
            elif cat == "scam":
                if item_lower in t_lower:
                    return True, f"命中擦边/非目标岗位黑名单: 【{item}】"

            # 3. JD 正文深度硬门槛排除
            elif cat == "jd_body_exclude":
                if jd_lower and item_lower in jd_lower:
                    return True, f"命中JD正文硬性排除规则: 【{item}】"

        return False, ""

    def get_filter_matrix(self) -> dict:
        """读取四重黑名单完整矩阵及开关状态"""
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM filter_matrix ORDER BY category, id ASC").fetchall()

        matrix = {
            "outsourcing": [],
            "training": [],
            "scam": [],
            "jd_body_exclude": []
        }
        for r in rows:
            cat = r["category"]
            if cat in matrix:
                matrix[cat].append({
                    "id": r["id"],
                    "item_name": r["item_name"],
                    "is_enabled": bool(r["is_enabled"])
                })
        return matrix

    def add_filter_item(self, category: str, item_name: str) -> bool:
        """向指定分类添加黑名单关键词"""
        if not item_name or not item_name.strip():
            return False
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._get_conn() as conn:
            conn.execute("INSERT OR IGNORE INTO filter_matrix (category, item_name, is_enabled, created_at) VALUES (?, ?, 1, ?)", (category, item_name.strip(), now_str))
            conn.commit()
        return True

    def remove_filter_item(self, item_id: int) -> bool:
        """删除指定黑名单规则条目"""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM filter_matrix WHERE id = ?", (item_id,))
            conn.commit()
        return True

    def toggle_filter_item(self, item_id: int, is_enabled: bool) -> bool:
        """切换某条黑名单规则开关"""
        with self._get_conn() as conn:
            conn.execute("UPDATE filter_matrix SET is_enabled = ? WHERE id = ?", (1 if is_enabled else 0, item_id))
            conn.commit()
        return True

    def set_rag_config(self, min_match_score: int = 65, enable_rag: bool = True):
        """配置 RAG 门槛分数及是否启用"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._get_conn() as conn:
            conn.execute("UPDATE learned_profile SET min_match_score = ?, enable_rag_filter = ?, updated_at = ? WHERE id = 1", (min_match_score, 1 if enable_rag else 0, now_str))
            conn.commit()

    # ============================
    # 全渠道投递岗位知识库记录与检索 (支持自动打招呼与手动投递)
    # ============================
    def record_delivered_job(self, company: str, title: str, salary: str = "", job_url: str = "", job_id: str = "", boss_id: str = "", source: str = "manual", jd_text: str = "", delivered_at: str = None) -> bool:
        """
        将打招呼/沟通成功的岗位记录沉淀至 RAG 知识库
        自动根据 job_id / boss_id / (company + title) 去重
        """
        c_clean = (company or "").strip()
        t_clean = (title or "").strip()
        if not c_clean or not t_clean:
            return False

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        d_time = delivered_at or now_str

        with self._get_conn() as conn:
            is_exist = False
            if job_id and job_id.strip():
                row = conn.execute("SELECT id FROM delivered_jobs WHERE job_id = ? LIMIT 1", (job_id.strip(),)).fetchone()
                if row: is_exist = True
            if not is_exist and boss_id and boss_id.strip():
                row = conn.execute("SELECT id FROM delivered_jobs WHERE boss_id = ? LIMIT 1", (boss_id.strip(),)).fetchone()
                if row: is_exist = True
            if not is_exist:
                row = conn.execute("SELECT id FROM delivered_jobs WHERE company = ? AND title = ? LIMIT 1", (c_clean, t_clean)).fetchone()
                if row: is_exist = True

            if not is_exist:
                conn.execute("""
                INSERT INTO delivered_jobs (company, title, salary, job_url, job_id, boss_id, source, jd_text, delivered_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    c_clean,
                    t_clean,
                    (salary or "面议").strip(),
                    (job_url or "").strip(),
                    (job_id or "").strip(),
                    (boss_id or "").strip(),
                    (source or "manual").strip(),
                    (jd_text or "").strip(),
                    d_time,
                    now_str
                ))
                conn.commit()
                return True
        return False

    def get_delivered_jobs(self, limit: int = 50, offset: int = 0) -> list[dict]:
        """获取已沉淀在知识库中的全量投递记录"""
        with self._get_conn() as conn:
            rows = conn.execute("""
            SELECT id, company, title, salary, job_url, job_id, boss_id, source, jd_text, delivered_at, created_at
            FROM delivered_jobs ORDER BY id DESC LIMIT ? OFFSET ?
            """, (limit, offset)).fetchall()
            return [dict(r) for r in rows]

    def get_delivered_jobs_count(self) -> dict:
        """获取投递统计数据"""
        with self._get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) as cnt FROM delivered_jobs").fetchone()["cnt"]
            manual = conn.execute("SELECT COUNT(*) as cnt FROM delivered_jobs WHERE source = 'manual'").fetchone()["cnt"]
            bot = conn.execute("SELECT COUNT(*) as cnt FROM delivered_jobs WHERE source = 'bot'").fetchone()["cnt"]
            return {"total": total, "manual": manual, "bot": bot}

    def sync_history_csv_to_db(self, history_csv_path: str) -> int:
        """将 history.csv 中的历史投递数据全量导入 SQLite delivered_jobs 知识库"""
        if not os.path.exists(history_csv_path):
            return 0
        added_count = 0
        try:
            with open(history_csv_path, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                for row in reader:
                    if row and len(row) >= 4:
                        dt_s = row[0].strip() if len(row) > 0 else ""
                        c = row[1].strip() if len(row) > 1 else ""
                        t = row[2].strip() if len(row) > 2 else ""
                        s = row[3].strip() if len(row) > 3 else "面议"
                        u = row[4].strip() if len(row) > 4 else ""
                        src = row[5].strip() if len(row) > 5 else "manual"
                        if c and t:
                            if self.record_delivered_job(company=c, title=t, salary=s, job_url=u, source=src, delivered_at=dt_s):
                                added_count += 1
        except Exception:
            pass
        return added_count

    # ============================
    # 用户人机偏好对齐训练样本库 (持久化累积增量学习)
    # ============================
    def add_job_feedback(self, title: str, company: str, salary: str = "", decision: str = "accept", reasons: list = None, company_type: str = "", category_tag: str = "") -> bool:
        """持久化保存用户对模拟岗位的判定样本（增量累加，不覆盖历史，滚雪球式越来越准）"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        reasons_json = json.dumps(reasons or [], ensure_ascii=False)
        with self._get_conn() as conn:
            conn.execute("""
            INSERT INTO user_job_feedback (title, company, salary, decision, reasons, company_type, category_tag, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                title.strip(),
                company.strip(),
                salary.strip(),
                decision.strip(),
                reasons_json,
                company_type.strip(),
                category_tag.strip(),
                now_str
            ))
            conn.commit()
        return True

    def get_all_job_feedbacks(self) -> list[dict]:
        """获取用户所有历史累积的偏好对齐样本"""
        with self._get_conn() as conn:
            rows = conn.execute("SELECT id, title, company, salary, decision, reasons, company_type, category_tag, created_at FROM user_job_feedback ORDER BY id ASC").fetchall()
            res = []
            for r in rows:
                d = dict(r)
                try:
                    d["reasons"] = json.loads(d.get("reasons") or "[]")
                except Exception:
                    d["reasons"] = []
                res.append(d)
            return res

    def get_feedback_stats(self) -> dict:
        """获取当前偏好对齐样本库统计"""
        with self._get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) as cnt FROM user_job_feedback").fetchone()["cnt"]
            acc = conn.execute("SELECT COUNT(*) as cnt FROM user_job_feedback WHERE decision = 'accept'").fetchone()["cnt"]
            rej = conn.execute("SELECT COUNT(*) as cnt FROM user_job_feedback WHERE decision = 'reject'").fetchone()["cnt"]
            return {"total": total, "accept": acc, "reject": rej}

    def clear_job_feedbacks(self) -> bool:
        """清空历史对齐反馈（仅当用户主动要求重新开始微调时调用）"""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM user_job_feedback")
            conn.commit()
        return True

    def add_chat_memory(self, role: str, content: str, memory_tags: list = None) -> int:
        """存储用户与 AI 对齐对话记录与记忆标签"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._get_conn() as conn:
            cur = conn.execute("""
            INSERT INTO ai_chat_memories (role, content, memory_tags, created_at)
            VALUES (?, ?, ?, ?)
            """, (role, content, json.dumps(memory_tags or [], ensure_ascii=False), now_str))
            conn.commit()
            return cur.lastrowid

    def get_chat_memories(self, limit: int = 30) -> list[dict]:
        """获取最近的历史对话记录"""
        with self._get_conn() as conn:
            rows = conn.execute("""
            SELECT * FROM ai_chat_memories ORDER BY id ASC LIMIT ?
            """, (limit,)).fetchall()
            res = []
            for r in rows:
                tags = []
                try: tags = json.loads(r["memory_tags"] or '[]')
                except Exception: pass
                res.append({
                    "id": r["id"],
                    "role": r["role"],
                    "content": r["content"],
                    "memory_tags": tags,
                    "created_at": r["created_at"]
                })
            return res

    def clear_chat_memories(self) -> bool:
        """清空对话历史"""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM ai_chat_memories")
            conn.commit()
        return True


# ==============================================================================
# DeepSeek 智能微调与偏好对齐服务 (支持 DeepSeek-V3 / DeepSeek-R1)
# ==============================================================================
class DeepSeekService:
    """
    DeepSeek API 集成服务：
    1. 连通性测试 (Test Connection)
    2. 基于求职者画像生成模拟岗位数据集 (Simulated Job Generation)
    3. 基于用户判定二元标签提炼推荐搜索词与黑名单 (Preference Alignment & Filter Recommendation)
    """
    def __init__(self, api_key: str = "", base_url: str = "https://api.deepseek.com", model: str = "deepseek-chat"):
        self.api_key = (api_key or "").strip()
        self.base_url = (base_url or "https://api.deepseek.com").rstrip("/")
        self.model = model or "deepseek-chat"

    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 6)

    def test_connection(self) -> dict:
        """测试 DeepSeek 接口连通性"""
        if not self.is_configured():
            return {"success": False, "message": "未配置有效的 DeepSeek API Key"}

        import requests
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "你是一位求职招聘助手。请回复极简短的一句话。"},
                {"role": "user", "content": "请测试接口连通性，简短回复确认。"}
            ],
            "max_tokens": 60,
            "temperature": 0.3
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                reply = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                return {"success": True, "message": reply or "DeepSeek 连通成功！", "model": self.model}
            else:
                return {"success": False, "message": f"HTTP {resp.status_code}: {resp.text[:180]}"}
        except Exception as e:
            return {"success": False, "message": f"连接异常: {e}"}

    def generate_simulated_jobs(self, resume_profile: dict, learned_profile: dict, count: int = 6, history_csv_path: str = None) -> list[dict]:
        """
        基于简历画像与 500+ 篇真实投递历史语料库，调用 DeepSeek 生成高度真实、工业级完整的 BOSS 直聘模拟岗位。
        包含：正向高匹配岗位、边界模糊岗位、反向陷阱岗位（外包/培训/假AI）
        输出完整的岗位职责、任职资格、团队福利与技术标签云。
        """
        if not self.is_configured():
            raise ValueError("未配置有效的 DeepSeek API Key")

        import requests
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        edu = resume_profile.get("education", "本科")
        skills = ", ".join(resume_profile.get("tech_skills", [])[:18]) or "Python, AI Agent, LangChain, RAG, FastAPI, Spring"
        titles = ", ".join(resume_profile.get("target_titles", [])) or "AI大模型应用开发, AI Agent开发, Python工程师"
        exp = resume_profile.get("experience_years", 0.5)

        pos_words = ", ".join(learned_profile.get("positive_keywords", [])[:10])
        sal = learned_profile.get("salary_bracket", "150-250元/天 | 6-10K")
        pref_titles = ", ".join(learned_profile.get("preferred_titles", [])[:6])

        # 读取 500+ 真实投递历史样本作为真实招聘语料参考
        real_companies_sample = []
        real_titles_sample = []
        if history_csv_path and os.path.exists(history_csv_path):
            try:
                with open(history_csv_path, "r", encoding="utf-8-sig") as f:
                    r = csv.reader(f)
                    next(r, None)
                    c_list, t_list = [], []
                    for row in r:
                        if len(row) >= 3:
                            if row[1].strip(): c_list.append(row[1].strip())
                            if row[2].strip(): t_list.append(row[2].strip())
                    real_companies_sample = [c for c, _ in Counter(c_list).most_common(25)]
                    real_titles_sample = [t for t, _ in Counter(t_list).most_common(20)]
            except Exception:
                pass

        ref_comps_str = ", ".join(real_companies_sample) if real_companies_sample else "腾讯, 快手, 百度, 智谱华章, 深信服, 智源人工智能研究院, 投肯无限, 富联康物流"
        ref_titles_str = ", ".join(real_titles_sample) if real_titles_sample else "AI Agent 开发实习生, ai应用开发工程师, 大模型 Agent 研发实习生, Python开发"

        sys_prompt = (
            "你是一位中国招聘领域资深猎头与求职匹配算法专家。\n"
            "你的任务是根据求职者的真实简历画像、以及求职者实际投递过的 500+ 个岗位的真实招聘语料，生成逼真、详细、工业级完整度的 BOSS 直聘模拟岗位。\n"
            "【极为重要】：真实 BOSS 直聘的岗位描述绝不是一句简写，必须包含详尽具体、层次分明的【岗位职责】（3~4条具体业务）和【任职资格】（3~4条具体技能与经历要求），以及真实的团队福利待遇和标签。\n"
            "必须严格输出合法的 JSON 格式，不要返回任何 Markdown 解释文字。"
        )

        user_prompt = f"""
当前求职者画像：
- 学历: {edu}
- 核心技术栈: {skills}
- 意向方向: {titles}
- 实战年限: {exp} 年 (2027届在校实习/应届毕业生)
- 历史投递偏好画像:
  - 正向偏好词: {pos_words}
  - 期望待遇区间: {sal}
  - 核心偏好岗位: {pref_titles}
- 求职者实际投递过的 500+ 个岗位中提炼的企业名录与岗位样本（供你逼真模仿参考）：
  - 曾投递代表企业: {ref_comps_str}
  - 曾投递代表岗位名: {ref_titles_str}

请为该求职者生成 {count} 个极具代表性、具体逼真、介绍详尽完整的 BOSS 直聘模拟岗位：
1. 包含 2 个【高度契合岗位】(核心做 AI Agent / RAG 应用 / LangChain 落地，技术真实落地，待遇匹配，符合在校实习身份)
2. 包含 2 个【边界模糊岗位】(例如传统Web后端挂大模型噱头、或数据标注清洗却叫AI应用运营、或经验要求偏高但技术栈符合)
3. 包含 2 个【典型陷阱岗位】(例如外包驻场派遣、招转培训实训机构、或纯电话销售客服挂羊头卖狗肉的虚假岗)

请严格输出 JSON 对象（responsibilities 和 requirements 必须包含具体的条目列表，不能简写）：
{{
  "jobs": [
    {{
      "id": 1,
      "title": "逼真具体的岗位名称 (如: AI Agent 应用研发实习生)",
      "company": "企业名称 (参考真实企业画像，如: 智谱华章 / 某AIGC独角兽 / 某驻场外包软件)",
      "company_type": "企业性质 (如: AIGC独角兽 / 上市公司 / 外包派遣公司 / IT实训机构)",
      "company_scale": "企业规模与轮次 (如: 100-499人 · B轮 / 10000人以上 · 上市公司 / 20人以下 · 初创)",
      "salary": "薪资待遇 (如: 200-250元/天 或 8-12K)",
      "city": "城市与商圈 (如: 杭州 · 西湖区 / 深圳 · 南山区 / 全国远程)",
      "category_type": "分类编码 (high_match / borderline / negative_trap)",
      "category_tag": "分类标签 (如: 🌟高度契合 / ⚖️边界案例 / ⚠️陷阱慎选)",
      "tech_tags": ["LangChain", "FastAPI", "Python", "RAG", "Agent"],
      "responsibilities": [
        "1. 负责基于 LangChain / LangGraph 构建企业级 AI Agent 工作流与多智能体协同机制;",
        "2. 负责 RAG 知识库检索增强链路的搭建、向量召回（Embedding + Rerank）精度调优;",
        "3. 参与大模型 Tool Use / Function Calling 外部工具插件与企业 API 对接;",
        "4. 持续优化 Prompt 提示词工程，提升复杂业务场景下的推理准确率与输出稳定性。"
      ],
      "requirements": [
        "1. 统招本科及以上学历在读，计算机、软件工程、人工智能等相关专业（2026/2027届优先）；",
        "2. 扎实的 Python 编程功底，熟悉 FastAPI/Flask 等主流 Web 开发框架；",
        "3. 深入理解大模型生态，熟悉 LangChain/LlamaIndex 等框架，具备实际项目落地经验；",
        "4. 每周可出勤 4 天以上，可连续实习 3~6 个月，具备强烈的技术热情与学习敏锐度。"
      ],
      "benefits": ["双休不加班", "转正机会", "导师一对一", "免费下午茶餐补", "大模型实战落地"],
      "ai_analysis": "AI推荐初衷与考察点说明：该岗位技术栈与您的简历高度契合，重点考查你对该类岗位在校实习的接受度。"
    }}
  ]
}}
"""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.7
        }
        if "chat" in self.model:
            payload["response_format"] = {"type": "json_object"}

        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"DeepSeek 接口响应异常: {resp.status_code} - {resp.text[:200]}")

        res_json = resp.json()
        content = res_json.get("choices", [{}])[0].get("message", {}).get("content", "")
        clean_c = re.sub(r'^```json\s*', '', content.strip(), flags=re.MULTILINE)
        clean_c = re.sub(r'```$', '', clean_c.strip(), flags=re.MULTILINE).strip()

        data = json.loads(clean_c)
        jobs = data.get("jobs", [])
        return jobs

    def analyze_preferences_and_recommend_filters(self, resume_profile: dict, feedback_list: list[dict], current_config: dict) -> dict:
        """
        基于用户在模拟岗位上的“符合/不符合+排除原因”反馈，结合简历画像，
        调用 DeepSeek 进行精准偏好聚类，生成推荐的检索意向词、配额比例及多层黑名单。
        """
        if not self.is_configured():
            raise ValueError("未配置有效的 DeepSeek API Key")

        import requests
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        # 整理反馈样本
        pos_feedbacks = []
        neg_feedbacks = []
        for item in feedback_list:
            decision = item.get("decision")
            j_title = item.get("title", "")
            j_comp = item.get("company", "")
            j_sal = item.get("salary", "")
            reasons = ", ".join(item.get("reasons", [])) or "不符意向"
            if decision == "accept":
                pos_feedbacks.append(f"【喜欢】{j_title} | {j_comp} | {j_sal}")
            else:
                neg_feedbacks.append(f"【排除】{j_title} | {j_comp} | 原因: {reasons}")

        fb_text = "用户标注的正向满意岗位：\n" + ("\n".join(pos_feedbacks) if pos_feedbacks else "暂无") + "\n\n"
        fb_text += "用户标注的坚决排除岗位：\n" + ("\n".join(neg_feedbacks) if neg_feedbacks else "暂无")

        sys_prompt = (
            "你是一位资深求职招聘算法专家。\n"
            "你的任务是根据求职者对模拟岗位的二元判定与排除原因，结合其简历画像，提炼出高度精准的 BOSS 直聘全自动打招呼过滤配置规则。\n"
            "必须严格输出合法的 JSON 格式，不要返回任何多余的 Markdown 或解释文字。"
        )

        user_prompt = f"""
求职者画像：
- 学历: {resume_profile.get('education', '本科')}
- 掌握核心技术: {', '.join(resume_profile.get('tech_skills', [])[:15])}

用户针对模拟岗位的实际反馈数据：
{fb_text}

系统当前已有配置：
- 意向关键词: {current_config.get('keywords', '')}
- 标题屏蔽词: {current_config.get('title_blacklist', '')}
- 城市白名单/黑名单: {current_config.get('city_name', '全国')}

请综合推断求职者的心智模型与真实求职痛点，输出最优的配置升级方案，严格遵循以下 JSON 结构：
{{
  "analysis_summary": "求职者偏好与排除特征深度分析 (150字以内，点明喜欢什么、坚决不要什么)",
  "recommended_keywords": "优化后的意向检索词组合 (英文逗号分隔，按优先级排序，如: AI Agent, 大模型应用开发, Python)",
  "keyword_weights": "各关键词推荐配额说明 (如: AI Agent(50%), 大模型应用开发(30%), Python(20%))",
  "title_blacklist_to_add": ["建议追加的岗位标题屏蔽词1", "屏蔽词2", "屏蔽词3", "屏蔽词4"],
  "company_blacklist_to_add": ["建议追加的公司/机构屏蔽词1", "屏蔽词2"],
  "jd_blacklist_to_add": ["建议追加的详情JD负向屏蔽词1", "屏蔽词2"],
  "salary_recommendation": "推荐薪资筛选设定 (如: 150-250元/天 或 4-8K)",
  "optimization_tips": ["防封与精准投递贴士1", "贴士2", "贴士3"]
}}
"""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.4
        }
        if "chat" in self.model:
            payload["response_format"] = {"type": "json_object"}

        resp = requests.post(url, json=payload, headers=headers, timeout=25)
        if resp.status_code != 200:
            raise RuntimeError(f"DeepSeek 接口响应异常: {resp.status_code} - {resp.text[:200]}")

        res_json = resp.json()
        content = res_json.get("choices", [{}])[0].get("message", {}).get("content", "")
        clean_c = re.sub(r'^```json\s*', '', content.strip(), flags=re.MULTILINE)
        clean_c = re.sub(r'```$', '', clean_c.strip(), flags=re.MULTILINE).strip()

        return json.loads(clean_c)

    def chat_alignment(self, user_message: str, resume_profile: dict, current_config: dict, chat_history: list = None) -> dict:
        """
        AI 偏好自然语言对话记忆与调优引擎：
        接收用户的自然语言纠偏指令（如：“腾讯那个AI实习虽然只有71分但其实可以投递”、“少于8K的外包不要，但自研6K可以”），
        让 AI 理解其意图，提取结构化规则并回复。
        """
        if not self.is_configured():
            return {
                "reply": "⚠️ 请先在上方配置有效的 DeepSeek API Key 后再进行偏好对齐对话。",
                "learned_rules": []
            }

        import requests
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        sys_prompt = (
            "你是一位资深求职招聘助手与求职偏好记忆中枢。\n"
            "用户正在对系统自动筛选出的岗位进行自然语言反馈与偏好纠偏。\n"
            "你的任务是：\n"
            "1. 深刻理解用户的纠偏意图与隐含心智（例如用户认可某些大厂、放宽某些技术栈的年限门槛、或者收紧某些隐性外包规则）。\n"
            "2. 总结出 1-3 条高度精炼的记忆规则（如：'优先放行大厂AI实习岗位'、'放宽Agent技术栈的年限要求至3年'、'排除纯客服/电话销售'）。\n"
            "3. 给出温暖、专业、确认式的回答，说明你记住了什么、将在后续筛选中如何智能调整。\n"
            "请严格以 JSON 格式输出：\n"
            "{\n"
            '  "reply": "对用户的回复说明 (150字以内，语气专业亲切，明确告知系统已记住并如何执行)",\n'
            '  "learned_rules": ["提取的规则1", "提取的规则2"],\n'
            '  "suggested_keyword_add": ["若建议补充搜索词则填，否则为空数组"],\n'
            '  "suggested_blacklist_add": ["若建议补充黑名单则填，否则为空数组"]\n'
            "}"
        )

        messages = [{"role": "system", "content": sys_prompt}]
        if chat_history:
            for item in chat_history[-4:]:
                messages.append({"role": item.get("role", "user"), "content": item.get("content", "")})

        user_content = (
            f"求职者简历核心技能: {', '.join(resume_profile.get('tech_skills', [])[:12])}\n"
            f"求职者学历: {resume_profile.get('education', '本科')}\n"
            f"当前关键词: {current_config.get('keywords', '')}\n"
            f"用户纠偏与指令内容: {user_message}"
        )
        messages.append({"role": "user", "content": user_content})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.4
        }
        if "chat" in self.model:
            payload["response_format"] = {"type": "json_object"}

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=25)
            if resp.status_code == 200:
                data = resp.json()
                raw_c = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                clean_c = re.sub(r'^```json\s*', '', raw_c.strip(), flags=re.MULTILINE)
                clean_c = re.sub(r'```$', '', clean_c.strip(), flags=re.MULTILINE).strip()
                res = json.loads(clean_c)
                return {
                    "reply": res.get("reply", "我已记住您的偏好，后续将为您调整！"),
                    "learned_rules": res.get("learned_rules", []),
                    "suggested_keyword_add": res.get("suggested_keyword_add", []),
                    "suggested_blacklist_add": res.get("suggested_blacklist_add", [])
                }
            else:
                return {
                    "reply": f"AI 服务响应异常 (HTTP {resp.status_code}): {resp.text[:120]}",
                    "learned_rules": []
                }
        except Exception as e:
            return {
                "reply": f"调用 AI 模型异常: {e}",
                "learned_rules": []
            }

