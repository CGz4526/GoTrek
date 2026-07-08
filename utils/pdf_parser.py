import pdfplumber
import re
from typing import Optional


def extract_text_from_pdf(pdf_path: str) -> Optional[str]:
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text.strip()
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return None


def extract_project_descriptions(resume_text: str) -> list:
    project_sections = []
    
    patterns = [
        r'(?:项目经验|项目经历|工作经历|项目简介|项目描述).*?(?=\n\n教育背景|教育经历|技能|证书|自我评价|\Z)',
        r'(?:负责|参与|主导).*?(?=\n\n|\Z)',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, resume_text, re.DOTALL)
        project_sections.extend([m.strip() for m in matches if len(m.strip()) > 50])
    
    return project_sections


def parse_project_from_description(description: str) -> dict:
    project = {
        'name': '',
        'description': description,
        'tech_stack': [],
        'project_type': '',
        'domain_tags': []
    }
    
    name_patterns = [
        r'项目名称[：:]?(.*?)\n',
        r'项目名[：:]?(.*?)\n',
        r'项目[：:]?(.*?)\n',
        r'(.*?)项目'
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, description)
        if match:
            project['name'] = match.group(1).strip()
            break
    
    tech_keywords = {
        'java': ['java', 'spring', 'springboot', 'mybatis', 'jdk', 'jvm'],
        'python': ['python', 'django', 'flask', 'fastapi', 'tensorflow', 'pytorch'],
        'go': ['go', 'golang', 'gin', 'echo'],
        'nodejs': ['node', 'nodejs', 'express', 'koa'],
        'mysql': ['mysql', 'mariadb', 'innodb'],
        'redis': ['redis', 'redisson'],
        'mongodb': ['mongodb', 'nosql'],
        'postgresql': ['postgresql', 'pg'],
        'rabbitmq': ['rabbitmq', '消息队列', 'mq'],
        'kafka': ['kafka', 'stream'],
        'docker': ['docker', '容器'],
        'kubernetes': ['kubernetes', 'k8s'],
        'nginx': ['nginx', '负载均衡'],
        'git': ['git', '版本控制'],
        'linux': ['linux', 'centos', 'ubuntu']
    }
    
    desc_lower = description.lower()
    for tech, keywords in tech_keywords.items():
        if any(keyword in desc_lower for keyword in keywords):
            project['tech_stack'].append(tech)
    
    type_keywords = {
        'ecommerce': ['电商', '购物', '商城', '交易', '支付'],
        'seckill': ['秒杀', '抢购', '限量'],
        'social': ['社交', '聊天', '论坛', '社区'],
        'cms': ['内容管理', 'cms', '博客', '新闻'],
        'crm': ['客户管理', 'crm', '销售'],
        'erp': ['erp', '企业资源', '管理系统'],
        'saas': ['saas', '软件即服务'],
        'data': ['数据', '大数据', '分析', '报表'],
        'ai': ['人工智能', '机器学习', '深度学习', '推荐'],
        'game': ['游戏', '手游', '端游'],
        'iot': ['物联网', 'iot', '设备']
    }
    
    for proj_type, keywords in type_keywords.items():
        if any(keyword in description for keyword in keywords):
            project['project_type'] = proj_type
            project['domain_tags'].append(proj_type)
            break
    
    if not project['project_type']:
        project['project_type'] = 'other'
    
    return project