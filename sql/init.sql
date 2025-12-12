-- 데이터베이스 생성
CREATE DATABASE dearai;

-- 데이터베이스 사용
USE dearai;

-- user 테이블 생성
CREATE TABLE user (
    id CHAR(36) NOT NULL,
    time_created DATETIME NOT NULL,
    filter_keyword JSON NULL,
    time_modified DATETIME NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    refresh_token VARCHAR(512) DEFAULT NULL,
    PRIMARY KEY (id)
);

-- email_lists 테이블 생성
CREATE TABLE recipient_lists (
    id CHAR(36) NOT NULL,
    email VARCHAR(255) NULL,
    recipient_name VARCHAR(255) NULL,
    recipient_group VARCHAR(255) NULL,
    time_modified DATETIME NULL,
    user_id CHAR(36) NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (user_id) REFERENCES user(id)
);

-- inputs 테이블 생성
CREATE TABLE inputs (
    id CHAR(36) NOT NULL,
    input_data JSON NULL,
    time_requested DATETIME NULL,
    recipient_id CHAR(36) NULL,
    recipient_email VARCHAR(255) NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (recipient_id) REFERENCES recipient_lists(id)
);

-- results 테이블 생성
CREATE TABLE results (
    id CHAR(36) NOT NULL,
    result_data JSON NULL,
    time_returned DATETIME NULL,
    input_id CHAR(36) NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (input_id) REFERENCES inputs(id)
);