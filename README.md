# DearAI-Back
메일 검수 프로그램 백

``` mermaid
classDiagram
%% ================== Clients / Gateway ==================
class ChromeExtension {
  <<React.js>>
  +requestData()
  +displayData()
}

%% ================== Backend Core ==================
class WebApplicationServer {
  <<FastAPI>>
  +authWithGoogle()
  +getContacts()
  +createContact()
  +createInput()
  +getResult(inputId)
  +enqueueForAI(inputData)
}

class OAuthServer {
  <<Google OAuth2.0>>
  +authorize()
  +issueTokens()
}

%% ================== Infra / Workers ==================
class MessageQueue {
  <<RabbitMQ>>
  +publish(inputData)
  +consume()
}

class AIAPIWorker {
  <<Worker>>
  +consumeFromQueue()
  +callGPTAPI()
  +storeGeneratedData()
}

%% ================== Persistence Layer ==================
class Database {
  <<MySQL>>
}

%% ---- Domain tables inside Database (from code) ----
class User {
  +id: str
  +email: str
  +refresh_token: str
  +filter_keyword: str?
  +time_created: datetime
  +time_modified: datetime
}

class Recipient_lists {
  +id: str
  +user_id: str
  +email: str
  +recipient_name: str
  +recipient_group: str?
}

class Inputs {
  +id: str
  +recipient_id: str
  +data: dict
}

class Results {
  +id: str
  +input_id: str
}

%% ================== Relationships (Data/Control flow) ==================
%% Client <-> Server
ChromeExtension <--> WebApplicationServer : HTTP/JSON\n데이터 요청/반환

%% Auth
WebApplicationServer --> OAuthServer : 인증 요청
OAuthServer --> WebApplicationServer : 인증 정보 반환\n(토큰/프로필)

%% DB I/O
WebApplicationServer --> Database : 데이터 저장/조회
Database ..> WebApplicationServer : 데이터 반환

%% MQ & Worker
WebApplicationServer --> MessageQueue : 메일 수정/생성 위한 정보 전달
MessageQueue --> AIAPIWorker : 적재 데이터 전달(consume)
AIAPIWorker --> Database : 생성한 데이터 저장
AIAPIWorker ..> WebApplicationServer : (선택) 상태콜백/웹훅

%% Database composition
Database o-- User
Database o-- Recipient_lists
Database o-- Inputs
Database o-- Results

%% Domain relations
User "1" --> "many" Recipient_lists : user_id(FK)
Recipient_lists "1" --> "many" Inputs : recipient_id(FK)
Inputs "1" --> "0..1" Results : input_id(FK)

%% Server uses domain models
WebApplicationServer ..> User : uses
WebApplicationServer ..> Recipient_lists : uses
WebApplicationServer ..> Inputs : uses
WebApplicationServer ..> Results : uses
```