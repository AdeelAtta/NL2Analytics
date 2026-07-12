#!/bin/bash
set -e

# ============================================================
# Seed titanic database
# ============================================================
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE titanic;
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname titanic <<-EOSQL
    CREATE TABLE passenger (
        passengerid INTEGER PRIMARY KEY,
        survived DOUBLE PRECISION,
        pclass INTEGER,
        name TEXT,
        sex TEXT,
        age DOUBLE PRECISION,
        sibsp INTEGER,
        parch INTEGER,
        ticket TEXT,
        fare DOUBLE PRECISION,
        cabin TEXT,
        embarked TEXT
    );

    INSERT INTO passenger VALUES
    (1,0,3,'Braund, Mr. Owen Harris','male',22,1,0,'A/5 21171',7.25,NULL,'S'),
    (2,1,1,'Cumings, Mrs. John Bradley (Florence Briggs Thayer)','female',38,1,0,'PC 17599',71.2833,'C85','C'),
    (3,1,3,'Heikkinen, Miss. Laina','female',26,0,0,'STON/O2. 3101282',7.925,NULL,'S'),
    (4,1,1,'Futrelle, Mrs. Jacques Heath (Lily May Peel)','female',35,1,0,'113803',53.1,'C123','S'),
    (5,0,3,'Allen, Mr. William Henry','male',35,0,0,'373450',8.05,NULL,'S'),
    (6,0,3,'Moran, Mr. James','male',NULL,0,0,'330877',8.4583,NULL,'Q'),
    (7,0,1,'McCarthy, Mr. Timothy J','male',54,0,0,'17463',51.8625,'E46','S'),
    (8,0,3,'Palsson, Master. Gosta Leonard','male',2,3,1,'349909',21.075,NULL,'S'),
    (9,1,3,'Johnson, Mrs. Oscar W (Elisabeth Vilhelmina Berg)','female',27,0,2,'347742',11.1333,NULL,'S'),
    (10,1,2,'Nasser, Mrs. Nicholas (Adele Achem)','female',14,1,0,'237736',30.0708,NULL,'C'),
    (11,1,3,'Sandstrom, Miss. Marguerite Rut','female',4,1,1,'PP 9549',16.7,'G6','S'),
    (12,1,1,'Bonnell, Miss. Elizabeth','female',58,0,0,'113783',26.55,'C103','S'),
    (13,0,3,'Saundercock, Mr. William Henry','male',20,0,0,'A/5. 2151',8.05,NULL,'S'),
    (14,0,3,'Andersson, Mr. Anders Johan','male',39,1,5,'347082',31.275,NULL,'S'),
    (15,0,3,'Vestrom, Miss. Hulda Amanda Adolfina','female',14,0,0,'350406',7.8542,NULL,'S'),
    (16,1,2,'Hewlett, Mrs. (Mary D Kingcome)','female',55,0,0,'248706',16,NULL,'S'),
    (17,0,3,'Rice, Master. Eugene','male',2,4,1,'382652',29.125,NULL,'Q'),
    (18,1,2,'Williams, Mr. Charles Eugene','male',NULL,0,0,'244373',13,NULL,'S'),
    (19,0,3,'Vander Planke, Mrs. Julius (Emelia Maria Vandemoortele)','female',31,1,0,'345763',18,NULL,'S'),
    (20,1,3,'Masselmani, Mrs. Fatima','female',NULL,0,0,'2649',7.225,NULL,'C'),
    (21,0,2,'Fynney, Mr. Joseph J','male',35,0,0,'239865',26,NULL,'S'),
    (22,1,2,'Beesley, Mr. Lawrence','male',34,0,0,'248698',13,'D56','S'),
    (23,1,3,'McGowan, Miss. Anna "Annie"','female',15,0,0,'330923',8.0292,NULL,'Q'),
    (24,1,1,'Sloper, Mr. William Thompson','male',28,0,0,'113788',35.5,'A6','S'),
    (25,0,3,'Palsson, Miss. Torborg Danira','female',8,3,1,'349909',21.075,NULL,'S'),
    (26,1,3,'Asplund, Mrs. Carl Oscar (Selma Augusta Emilia Johansson)','female',38,1,5,'347077',31.3875,NULL,'S'),
    (27,0,3,'Emir, Mr. Farred Chehab','male',NULL,0,0,'2631',7.225,NULL,'C'),
    (28,0,1,'Fortune, Mr. Charles Alexander','male',19,3,2,'19950',263,'C23 C25 C27','S'),
    (29,1,3,'O''Dwyer, Miss. Ellen "Nellie"','female',NULL,0,0,'330959',7.8792,NULL,'Q'),
    (30,0,3,'Todoroff, Mr. Lalio','male',NULL,0,0,'349216',7.8958,NULL,'S');
EOSQL

# ============================================================
# Seed employees database
# ============================================================
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE employees;
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname employees <<-EOSQL
    CREATE TABLE departments (
        dept_no CHAR(4) PRIMARY KEY,
        dept_name VARCHAR(40) NOT NULL
    );

    CREATE TABLE employees (
        emp_no INTEGER PRIMARY KEY,
        birth_date DATE NOT NULL,
        first_name VARCHAR(14) NOT NULL,
        last_name VARCHAR(16) NOT NULL,
        gender CHAR(1) NOT NULL,
        hire_date DATE NOT NULL
    );

    CREATE TABLE dept_emp (
        emp_no INTEGER NOT NULL,
        dept_no CHAR(4) NOT NULL,
        from_date DATE NOT NULL,
        to_date DATE NOT NULL,
        PRIMARY KEY (emp_no, dept_no),
        FOREIGN KEY (emp_no) REFERENCES employees(emp_no),
        FOREIGN KEY (dept_no) REFERENCES departments(dept_no)
    );

    CREATE TABLE titles (
        emp_no INTEGER NOT NULL,
        title VARCHAR(50) NOT NULL,
        from_date DATE NOT NULL,
        to_date DATE,
        PRIMARY KEY (emp_no, title, from_date),
        FOREIGN KEY (emp_no) REFERENCES employees(emp_no)
    );

    CREATE TABLE salaries (
        emp_no INTEGER NOT NULL,
        salary INTEGER NOT NULL,
        from_date DATE NOT NULL,
        to_date DATE NOT NULL,
        PRIMARY KEY (emp_no, from_date),
        FOREIGN KEY (emp_no) REFERENCES employees(emp_no)
    );

    INSERT INTO departments VALUES
    ('d001','Marketing'),
    ('d002','Finance'),
    ('d003','Human Resources'),
    ('d004','Production'),
    ('d005','Development'),
    ('d006','Quality Management'),
    ('d007','Sales'),
    ('d008','Research'),
    ('d009','Customer Service');

    INSERT INTO employees VALUES
    (10001,'1953-09-02','Georgi','Facello','M','1986-06-26'),
    (10002,'1964-06-02','Bezalel','Simmel','F','1985-11-21'),
    (10003,'1959-12-03','Parto','Bamford','M','1986-08-28'),
    (10004,'1954-05-01','Chirstian','Koblick','M','1986-12-01'),
    (10005,'1955-01-21','Kyoichi','Maliniak','M','1989-09-12'),
    (10006,'1953-04-20','Anneke','Preusig','F','1989-06-02'),
    (10007,'1957-05-23','Tzvetan','Zielinski','F','1989-02-10'),
    (10008,'1958-02-19','Saniya','Kalloufi','M','1994-09-15'),
    (10009,'1952-04-19','Sumant','Peac','F','1985-02-18'),
    (10010,'1963-06-01','Duangkaew','Piveteau','F','1989-08-24');

    INSERT INTO dept_emp VALUES
    (10001,'d005','1986-06-26','9999-01-01'),
    (10002,'d007','1996-08-03','9999-01-01'),
    (10003,'d004','1995-12-03','9999-01-01'),
    (10004,'d004','1986-12-01','9999-01-01'),
    (10005,'d003','1989-09-12','9999-01-01'),
    (10006,'d005','1990-08-05','9999-01-01'),
    (10007,'d005','1989-02-10','9999-01-01'),
    (10008,'d005','1998-03-11','2000-07-31'),
    (10009,'d006','1985-02-18','9999-01-01'),
    (10010,'d005','1996-11-24','2000-06-26');

    INSERT INTO titles VALUES
    (10001,'Senior Engineer','1986-06-26','9999-01-01'),
    (10002,'Staff','1996-08-03','9999-01-01'),
    (10003,'Senior Engineer','1995-12-03','9999-01-01'),
    (10004,'Engineer','1986-12-01','1995-12-01'),
    (10004,'Senior Engineer','1995-12-01','9999-01-01'),
    (10005,'Senior Staff','1996-09-12','9999-01-01'),
    (10006,'Senior Engineer','1990-08-05','9999-01-01'),
    (10007,'Senior Staff','1996-02-11','9999-01-01'),
    (10008,'Assistant Engineer','1998-03-11','2000-07-31'),
    (10009,'Senior Engineer','1985-02-18','9999-01-01');

    INSERT INTO salaries VALUES
    (10001,60117,'1986-06-26','1987-06-26'),
    (10001,62102,'1987-06-26','1988-06-25'),
    (10002,65828,'1996-08-03','1997-08-03'),
    (10003,40006,'1995-12-03','1996-12-02'),
    (10004,40054,'1986-12-01','1987-12-01'),
    (10005,78228,'1989-09-12','1990-09-12'),
    (10006,40000,'1990-08-05','1991-08-05'),
    (10007,56724,'1989-02-10','1990-02-10'),
    (10008,46671,'1998-03-11','1999-03-11'),
    (10009,60929,'1985-02-18','1986-02-18');
EOSQL
