import re
import jieba


def split_text_into_questions(text: str) -> list:
    text = text.replace('\r', '\n')
    
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if line and len(line) > 5:
            cleaned_lines.append(line)
    
    questions = []
    current_question = ''
    
    for line in cleaned_lines:
        numbered_match = re.match(r'^\s*(?:\d+\s*\.\s*|\d+\s*、\s*|【\d+】\s*|\(\d+\)\s*|第\d+[题问]\s*)\s*(.*)', line)
        if numbered_match:
            if current_question and len(current_question.strip()) > 10:
                questions.append(current_question.strip())
            current_question = numbered_match.group(1)
        elif line.startswith(('问', '请问', '谈谈', '说说', '如何', '为什么', '什么是', '怎么', '能否', '举例说明', '描述', '解释', '分析')):
            if current_question and len(current_question.strip()) > 10:
                questions.append(current_question.strip())
            current_question = line
        else:
            if current_question:
                current_question += ' ' + line
    
    if current_question and len(current_question.strip()) > 10:
        questions.append(current_question.strip())
    
    if not questions:
        question_pattern = r'(?:问|问题|题目|请问|谈谈|说说|如何|为什么|什么是|怎么|能否|举例说明|描述|解释|分析).*?(?=。|？|！|\n\n|\Z)'
        matches = re.findall(question_pattern, text, re.DOTALL)
        questions = [q.strip() for q in matches if len(q.strip()) > 10]
    
    if not questions:
        questions = [text.strip()]
    
    return questions


def extract_keywords(text: str) -> list:
    jieba.load_userdict("utils/custom_dict.txt")
    words = jieba.lcut(text)
    
    stop_words = {'的', '是', '在', '和', '有', '我', '他', '她', '它', '这', '那', '了', '啊', '吗', '呢', '吧', '可以', '会', '就', '都', '要', '不', '去', '来', '说', '看', '听', '想', '做', '给', '对', '好', '能', '上', '下', '大', '小', '多', '少', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十'}
    
    keywords = []
    for word in words:
        if len(word) > 1 and word not in stop_words:
            keywords.append(word)
    
    return keywords


def clean_text(text: str) -> str:
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\s，。！？：；""''（）\-\.\_]', '', text)
    return text.strip()


def is_project_question(text: str) -> bool:
    project_keywords = ['项目', '系统', '平台', '架构', '设计', '开发', '实现', '优化', '改造', '重构', '模块', '功能', '需求', '流程']
    return any(keyword in text for keyword in project_keywords)


def is_bagua_question(text: str) -> bool:
    bagua_keywords = ['原理', '机制', '区别', '对比', '优缺点', '特性', '概念', '定义', '作用', '如何', '为什么', '什么是', '怎么', '区别', '比较']
    return any(keyword in text for keyword in bagua_keywords)


def is_algorithm_question(text: str) -> bool:
    algo_keywords = ['算法', '复杂度', '排序', '查找', '二叉树', '链表', '动态规划', '贪心', '回溯', '图', '最短路径', '哈希', '堆', '栈', '队列']
    return any(keyword in text for keyword in algo_keywords)


def classify_bagua_category(text: str) -> str:
    category_keywords = {
        'redis': ['redis', '缓存', '分布式缓存', 'key-value', '内存数据库'],
        'mysql': ['mysql', '数据库', 'sql', '索引', '事务', '锁', '主从', '分库分表'],
        'java': ['java', 'jvm', '虚拟机', 'gc', '垃圾回收', '类加载', '反射', '注解'],
        'multithreading': ['多线程', '并发', '线程池', '锁', 'synchronized', 'volatile', 'atomic', 'cas'],
        'collection': ['集合', 'list', 'map', 'set', 'arraylist', 'hashmap', 'linkedlist'],
        'network': ['网络', 'tcp', 'udp', 'http', 'https', 'socket', '三次握手', '四次挥手'],
        'os': ['操作系统', '进程', '线程', '调度', '内存管理', '文件系统'],
        'design_pattern': ['设计模式', '单例', '工厂', '观察者', '适配器', '策略', '模板方法'],
        'spring': ['spring', 'springboot', 'ioc', 'aop', '依赖注入', 'bean'],
        'distributed': ['分布式', '微服务', 'rpc', '服务发现', '熔断', '限流', '分布式锁', '分布式事务']
    }
    
    text_lower = text.lower()
    for category, keywords in category_keywords.items():
        if any(keyword in text_lower for keyword in keywords):
            return category
    
    return 'other'