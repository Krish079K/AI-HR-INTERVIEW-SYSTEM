import sqlite3
import pymysql
import pymysql.err
import os
from werkzeug.security import generate_password_hash
from config import Config

# Unified Database Exception wrapper
class DBIntegrityError(Exception):
    pass

class MySQLRow:
    """
    Adapter to wrap PyMySQL row tuples, supporting both index-based
    and case-insensitive key-based lookup, as well as dict conversion.
    """
    def __init__(self, raw_tuple, description):
        self._raw = raw_tuple
        self._keys = [col[0] for col in description] if description else []
        self._key_to_idx = {name: idx for idx, name in enumerate(self._keys)}
        # Case-insensitive mapping
        for idx, name in enumerate(self._keys):
            self._key_to_idx[name.lower()] = idx
            
    def __getitem__(self, key):
        if isinstance(key, int):
            return self._raw[key]
        elif isinstance(key, str):
            idx = self._key_to_idx.get(key)
            if idx is None:
                idx = self._key_to_idx.get(key.lower())
            if idx is not None:
                return self._raw[idx]
            raise KeyError(key)
        else:
            raise TypeError("Index must be int or str")
            
    def keys(self):
        return self._keys

    def values(self):
        return self._raw

    def items(self):
        return zip(self._keys, self._raw)

    def __iter__(self):
        return iter(self._raw)

    def __len__(self):
        return len(self._raw)

    def __repr__(self):
        return repr(dict(self.items()))


class QueryNormalizerCursor:
    def __init__(self, cursor, db_type):
        self.cursor = cursor
        self.db_type = db_type

    def execute(self, query, params=None):
        # PRAGMA commands are SQLite-specific, ignore them on MySQL
        if self.db_type == 'mysql' and 'PRAGMA' in query:
            return self

        # Normalize query placeholders and random function names
        if self.db_type == 'sqlite':
            query = query.replace('%s', '?')
            query = query.replace('ORDER BY RAND()', 'ORDER BY RANDOM()')
        else:
            query = query.replace('?', '%s')
            query = query.replace('ORDER BY RANDOM()', 'ORDER BY RAND()')

        try:
            if params is not None:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            return self
        except (sqlite3.IntegrityError, pymysql.err.IntegrityError) as e:
            raise DBIntegrityError(str(e))

    def executemany(self, query, seq_of_params):
        if self.db_type == 'sqlite':
            query = query.replace('%s', '?')
        else:
            query = query.replace('?', '%s')

        try:
            self.cursor.executemany(query, seq_of_params)
            return self
        except (sqlite3.IntegrityError, pymysql.err.IntegrityError) as e:
            raise DBIntegrityError(str(e))

    def fetchone(self):
        row = self.cursor.fetchone()
        if row is None:
            return None
        if self.db_type == 'mysql':
            return MySQLRow(row, self.cursor.description)
        return row

    def fetchall(self):
        rows = self.cursor.fetchall()
        if rows is None:
            return []
        if self.db_type == 'mysql':
            desc = self.cursor.description
            return [MySQLRow(row, desc) for row in rows]
        return rows

    @property
    def lastrowid(self):
        return self.cursor.lastrowid

    def __getattr__(self, name):
        return getattr(self.cursor, name)


class QueryNormalizerConnection:
    def __init__(self, conn, db_type):
        self.conn = conn
        self.db_type = db_type

    def cursor(self):
        raw_cursor = self.conn.cursor()
        return QueryNormalizerCursor(raw_cursor, self.db_type)

    def commit(self):
        return self.conn.commit()

    def close(self):
        return self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __getattr__(self, name):
        return getattr(self.conn, name)


def get_db_connection():
    db_type = getattr(Config, 'DB_TYPE', 'sqlite')
    if db_type == 'mysql':
        host = getattr(Config, 'MYSQL_HOST', 'localhost')
        port = getattr(Config, 'MYSQL_PORT', 3306)
        user = getattr(Config, 'MYSQL_USER', 'root')
        password = getattr(Config, 'MYSQL_PASSWORD', '')
        database = getattr(Config, 'MYSQL_DB', 'ai_interviewer')
        
        try:
            raw_conn = pymysql.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=database
            )
        except pymysql.err.OperationalError as e:
            # Error 1049 is "Unknown database"
            if len(e.args) > 0 and e.args[0] == 1049:
                # Create the database first
                temp_conn = pymysql.connect(
                    host=host,
                    port=port,
                    user=user,
                    password=password
                )
                temp_cursor = temp_conn.cursor()
                temp_cursor.execute(f"CREATE DATABASE IF NOT EXISTS {database}")
                temp_conn.commit()
                temp_conn.close()
                # Connect to the newly created database
                raw_conn = pymysql.connect(
                    host=host,
                    port=port,
                    user=user,
                    password=password,
                    database=database
                )
            else:
                raise e
        return QueryNormalizerConnection(raw_conn, 'mysql')
    else:
        raw_conn = sqlite3.connect(Config.DATABASE)
        raw_conn.row_factory = sqlite3.Row
        return QueryNormalizerConnection(raw_conn, 'sqlite')


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    db_type = getattr(Config, 'DB_TYPE', 'sqlite')
    
    if db_type == 'mysql':
        # 1. Create Users Table (MySQL)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role VARCHAR(50) DEFAULT 'candidate',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        ''')
        
        # 2. Create Questions Table (MySQL)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            category VARCHAR(100) NOT NULL,
            question_text TEXT NOT NULL,
            keywords VARCHAR(500) NOT NULL,
            ideal_answer TEXT
        );
        ''')
        
        # 3. Create Interviews Table (MySQL)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS interviews (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            category VARCHAR(100) NOT NULL,
            status VARCHAR(50) DEFAULT 'in_progress',
            overall_score DOUBLE DEFAULT 0.0,
            confidence_score DOUBLE DEFAULT 0.0,
            technical_score DOUBLE DEFAULT 0.0,
            communication_score DOUBLE DEFAULT 0.0,
            eye_contact_score DOUBLE DEFAULT 0.0,
            feedback_summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        ''')
        
        # 4. Create Responses Table (MySQL)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS responses (
            id INT AUTO_INCREMENT PRIMARY KEY,
            interview_id INT NOT NULL,
            question_id INT NOT NULL,
            transcript TEXT,
            audio_path VARCHAR(500),
            speaking_speed DOUBLE DEFAULT 0.0,
            eye_contact_ratio DOUBLE DEFAULT 0.0,
            confidence_score DOUBLE DEFAULT 0.0,
            communication_score DOUBLE DEFAULT 0.0,
            technical_score DOUBLE DEFAULT 0.0,
            emotions_json TEXT,
            feedback TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (interview_id) REFERENCES interviews (id) ON DELETE CASCADE,
            FOREIGN KEY (question_id) REFERENCES questions (id)
        );
        ''')
    else:
        # Enable foreign keys in SQLite
        cursor.execute("PRAGMA foreign_keys = ON;")
        
        # 1. Create Users Table (SQLite)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'candidate',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        ''')
        
        # 2. Create Questions Table (SQLite)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            question_text TEXT NOT NULL,
            keywords TEXT NOT NULL,
            ideal_answer TEXT
        );
        ''')
        
        # 3. Create Interviews Table (SQLite)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS interviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            status TEXT DEFAULT 'in_progress',
            overall_score REAL DEFAULT 0.0,
            confidence_score REAL DEFAULT 0.0,
            technical_score REAL DEFAULT 0.0,
            communication_score REAL DEFAULT 0.0,
            eye_contact_score REAL DEFAULT 0.0,
            feedback_summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        ''')
        
        # 4. Create Responses Table (SQLite)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            interview_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            transcript TEXT,
            audio_path TEXT,
            speaking_speed REAL DEFAULT 0.0,
            eye_contact_ratio REAL DEFAULT 0.0,
            confidence_score REAL DEFAULT 0.0,
            communication_score REAL DEFAULT 0.0,
            technical_score REAL DEFAULT 0.0,
            emotions_json TEXT,
            feedback TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (interview_id) REFERENCES interviews (id) ON DELETE CASCADE,
            FOREIGN KEY (question_id) REFERENCES questions (id)
        );
        ''')
        
    # Seed default questions if empty
    cursor.execute("SELECT COUNT(*) FROM questions")
    if cursor.fetchone()[0] == 0:
        default_questions = [
            # HR Questions
            ('HR', 'Tell me about yourself.', 'background,experience,education,career,passion', 
             'I am a passionate software engineer with experience building web applications. I love solving complex problems, working in collaborative teams, and constantly learning new technologies.'),
            ('HR', 'What are your greatest strengths and weaknesses?', 'strength,weakness,improve,adaptability,problem-solving,growth', 
             'My strengths include strong analytical skills, adaptability, and visual communication. A weakness I have been actively working on is delegation, where I sometimes take on too much work myself, but I am learning to trust my teammates more.'),
            ('HR', 'Why should we hire you?', 'skills,value,contribution,fit,solve,experience', 
             'You should hire me because I possess a unique blend of technical proficiency and soft skills that match this role. I have hands-on experience, a strong work ethic, and a drive to contribute value to your projects from day one.'),
            ('HR', 'Where do you see yourself in five years?', 'future,goals,career,growth,leadership,learning', 
             'In five years, I see myself taking on leadership roles, contributing to core architecture decisions, and mentoring junior engineers while remaining hands-on with cutting-edge technologies.'),
            ('HR', 'What are your salary expectations and why?', 'salary,expectations,market,range,value,negotiable,flexible',
             'My salary expectations are aligned with the market rate for this role and my experience level. Based on my research and qualifications, a range of eighty thousand to one hundred thousand is fair, but I am open to negotiation based on the overall compensation package.'),
            ('HR', 'Why do you want to work for our company?', 'company,values,culture,mission,growth,opportunity,reputation',
             'I want to work for your company because I align with your mission and core values. Your reputation for innovation and supportive culture makes it the perfect place for me to grow my career and contribute to meaningful projects.'),
            ('HR', 'How do you handle pressure and stress?', 'pressure,stress,calm,organize,prioritize,exercise,focus',
             'I handle pressure by staying organized and prioritizing tasks. I break complex problems into smaller, manageable steps, maintain open communication with my team, and take brief breaks to clear my head and stay focused.'),
            ('HR', 'What motivates you to perform your best at work?', 'motivation,challenges,learning,results,impact,collaboration,success',
             'I am motivated by solving challenging problems and seeing the direct impact of my work on users. Collaboration with a talented team and the opportunity to continuously learn new technologies also drive me to excel.'),

            # Technical Coding Questions
            ('Technical Coding', 'What is the difference between SQL and NoSQL databases?', 'relational,non-relational,schema,scale,document,key-value,joins', 
             'SQL databases are relational, table-based, and have strict schemas, making them great for complex queries and ACID compliance. NoSQL databases are non-relational, document or key-value based, have dynamic schemas, and scale horizontally, making them suitable for unstructured data and massive scale.'),
            ('Technical Coding', 'Explain the concept of Object-Oriented Programming (OOP) and its key pillars.', 'inheritance,polymorphism,encapsulation,abstraction,classes,objects', 
             'Object-Oriented Programming is a paradigm centered around objects. Its four pillars are Encapsulation (hiding internal state), Abstraction (exposing only necessary details), Inheritance (reusing code from parent classes), and Polymorphism (allowing child classes to share behaviors in different forms).'),
            ('Technical Coding', 'What are RESTful APIs and how do they work?', 'http,stateless,methods,get,post,put,delete,json,uri', 
             'RESTful APIs are web services that follow representational state transfer constraints. They use HTTP methods like GET to retrieve, POST to create, PUT/PATCH to update, and DELETE to remove resources, communicating statelessly using standard formats like JSON.'),
            ('Technical Coding', 'What is time complexity, and why is it important in algorithm design?', 'big o,efficiency,performance,execution,scale,inputs,memory', 
             'Time complexity describes the execution time of an algorithm as a function of the input size, typically expressed in Big O notation. It is crucial for ensuring code scales efficiently and performs well under heavy data loads.'),
            ('Technical Coding', 'Explain the difference between a process and a thread.', 'process,thread,memory,cpu,execution,concurrency,sharing',
             'A process is an independent program in execution with its own allocated memory space. A thread is the smallest unit of execution within a process, sharing the parent process\'s memory and resources, making context switching faster but requiring synchronization.'),
            ('Technical Coding', 'What is the purpose of indexes in database management systems, and how do they work?', 'index,database,search,query,performance,b-tree,speed,read,write',
             'Indexes are used in databases to speed up data retrieval operations. They act like a book index, storing references to rows in data structures like B-Trees, which reduces query search time from linear scan to logarithmic lookup, though they add overhead to writes.'),
            ('Technical Coding', 'Explain the difference between synchronous and asynchronous programming.', 'synchronous,asynchronous,blocking,non-blocking,event loop,callbacks,promises,threads',
             'Synchronous programming executes operations sequentially, blocking execution until the current task completes. Asynchronous programming is non-blocking, allowing the program to initiate tasks like I/O and continue executing other code, handling results later via callbacks, promises, or async/await.'),
            ('Technical Coding', 'What is git, and how do you resolve merge conflicts?', 'git,version control,merge conflict,branches,repository,resolve,pull,commit',
             'Git is a distributed version control system. When two developers modify the same line in a file on different branches and merge, Git flags a merge conflict. I resolve it by opening the conflicting file, identifying the diff markers, discussing with the teammate if needed, selecting the correct code, staging the file, and committing.'),

            # Behavioral Questions
            ('Behavioral', 'Describe a challenge or conflict you faced in a team project and how you resolved it.', 'conflict,resolution,communication,collaboration,empathy,compromise', 
             'In a past team project, there was a disagreement on API design. I organized a meeting where everyone presented their pros and cons. We listened to each other, evaluated performance tradeoffs, and reached a compromise that met everyone\'s needs.'),
            ('Behavioral', 'Tell me about a time you failed and what you learned from it.', 'failure,mistake,responsibility,learning,reflection,improvement', 
             'I once missed a deployment deadline due to an unexpected integration bug. I took full responsibility, worked late to resolve the issue, and learned the value of writing comprehensive unit tests and doing staging builds earlier in the sprint cycle.'),
            ('Behavioral', 'Describe a situation where you had to work under a tight deadline.', 'deadline,pressure,prioritization,focus,planning,delivery', 
             'When a critical customer bug was escalated with a 24-hour SLA, I prioritized the issue, broke down the debugging process step-by-step, deferred other work, and successfully deployed a patch within 12 hours.'),
            ('Behavioral', 'How do you handle disagreement with a manager or senior team member?', 'respect,listen,evidence,professionalism,alignment,feedback', 
             'I handle disagreement by scheduling a 1-on-1 to discuss it. I listen to their perspective, present my arguments with clear data or code examples, and maintain professionalism. If we disagree, I respect their final decision and commit to aligning with the team\'s direction.'),
            ('Behavioral', 'Describe a time when you went above and beyond for a project or client.', 'extra,effort,initiative,exceeded,expectations,client,problem,value',
             'When a client reported a critical bug after business hours, I took the initiative to debug and patch the issue immediately. I not only fixed the bug but also set up an automated alert system to prevent it from happening again, exceeding the client\'s expectations.'),
            ('Behavioral', 'Tell me about a time you had to learn a new technology quickly to solve a problem.', 'learn,technology,quick,adapt,documentation,prototype,solved,fast',
             'For a project requiring real-time updates, I had to learn WebSockets within three days. I read the documentation, built a small proof-of-concept prototype, integrated it with our existing stack, and successfully met the delivery deadline.'),
            ('Behavioral', 'Describe a situation where you had to prioritize multiple competing tasks.', 'prioritize,tasks,urgency,importance,schedule,deadline,impact,organization',
             'When faced with three high-priority features due in the same week, I analyzed their business impact and urgency. I created a daily schedule, communicated potential delays to stakeholders early, focused on the highest-impact feature first, and successfully delivered all tasks.'),
            ('Behavioral', 'Tell me about a time you helped a coworker who was struggling with their workload.', 'help,coworker,support,teamwork,assistance,collaboration,workload',
             'A teammate was falling behind on their sprint tasks due to a complex bug. I volunteered to pair program with them for a few hours. We identified the root cause together, resolved the issue, and ensured our team met the sprint goal on time.'),

            # Aptitude Questions
            ('Aptitude', 'A car travels at a speed of sixty kilometers per hour. How far will it travel in three hours?', 'distance,travel,hundred,eighty,kilometers,speed,time,multiply',
             'The distance traveled is calculated by multiplying the speed by the time. Sixty kilometers per hour times three hours equals one hundred and eighty kilometers.'),
            ('Aptitude', 'If a product is sold at a twenty percent profit, what is the ratio of cost price to selling price?', 'ratio,cost price,selling price,five,six,percent,profit,fraction',
             'If the cost price is one hundred percent, a twenty percent profit makes the selling price one hundred and twenty percent. The ratio of cost price to selling price is five to six.'),
            ('Aptitude', 'The average age of five students is twenty years. If a new student joins and the average becomes twenty-one, what is the age of the new student?', 'average,age,twenty,six,years,sum,total',
             'The sum of ages of the five students is five times twenty, which is one hundred. With the new student, the total age for six students is six times twenty-one, which is one hundred and twenty-six. The new student is twenty-six years old.'),
            ('Aptitude', 'A train one hundred meters long passes a telegraph post in ten seconds. What is the speed of the train in kilometers per hour?', 'speed,train,meters,seconds,thirty,six,kilometers,hour,velocity',
             'The speed is distance divided by time, which is one hundred meters divided by ten seconds, equaling ten meters per second. Converting this to kilometers per hour by multiplying by three point six gives thirty-six kilometers per hour.'),
            ('Aptitude', 'If twelve men can complete a project in eight days, how many days will it take sixteen men to complete the same work?', 'men,days,work,six,inverse,proportion,math',
             'The total work is twelve men times eight days, which equals ninety-six man-days. If sixteen men work on it, the days required is ninety-six divided by sixteen, which is six days.'),
            ('Aptitude', 'A container holds forty liters of milk. Ten liters are removed and replaced with water. What is the ratio of milk to water now?', 'ratio,milk,water,three,one,liters,fraction,percentage',
             'When ten liters of milk are removed, thirty liters of milk remain. Replacing it with ten liters of water results in thirty liters of milk and ten liters of water. The ratio of milk to water is three to one.'),
            ('Aptitude', 'The price of a book increases by ten percent, and then decreases by ten percent. What is the net percentage change in the price?', 'percent,change,decrease,one,loss,math,net',
             'If the original price is one hundred, a ten percent increase makes it one hundred and ten. A subsequent ten percent decrease reduces the price by eleven, resulting in ninety-nine. The net change is a one percent decrease.'),
            ('Aptitude', 'A bag contains five red and seven blue balls. If a ball is drawn at random, what is the probability that it is red?', 'probability,red,five,twelve,fraction,chance,math',
             'The total number of balls is five red plus seven blue, which is twelve. The probability of drawing a red ball is the number of red balls divided by the total, which is five out of twelve.')
        ]
        cursor.executemany("INSERT INTO questions (category, question_text, keywords, ideal_answer) VALUES (?, ?, ?, ?)", default_questions)
        conn.commit()

    # Seed a default admin user if not exists
    cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
    if cursor.fetchone()[0] == 0:
        admin_pass = generate_password_hash("admin123")
        cursor.execute("INSERT INTO users (name, email, password_hash, role) VALUES ('System Admin', 'admin@interview.ai', ?, 'admin')", (admin_pass,))
        conn.commit()
        
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Database initialized successfully!")

