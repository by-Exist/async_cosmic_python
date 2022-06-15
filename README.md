# Async Cosmic Python

[파이썬으로 살펴보는 아키텍처 패턴](https://book.naver.com/bookdb/book_detail.nhn?bid=20554246)의 코드를 비동기로 전환하는 과정에서 만난 문제점들과 이를 해결한 방법에 대해 서술합니다.

## DDD 객체 설계

DDD 개념의 값객체, 엔티티, 에그리게잇의 정의에 python의 dataclasses, metaclass 및 typing.dataclass_transform을 사용하였습니다.

[기존 도메인 객체](https://github.com/cosmicpython/code/blob/master/src/allocation/domain/model.py)의 코드와 [Base](allocation/domain/models/bases.py), 구현([order_line](allocation/domain/models/order_line.py), [batch](allocation/domain/models/batch.py), [product](allocation/domain/models/product.py))의 코드를 확인하실 수 있습니다.

## SQLAlchemy ORM Mapping

sqlalchemy에서 orm을 통해 인스턴스를 가져올 경우 _sa_instance_state 속성을 객체에 부여하여 세션 내 객체의 상태 정보(임시, 보류, 영구, 삭제)를 저장합니다.

값 객체의 경우 dataclass의 frozen=True를 지정하였기 때문에 \_\_setattr__이 금지되도록 설계되어 있어 dataclasses.FrozenInstanceError 예외가 발생합니다. orm 매핑 시 구현 ValueObject의 \_\_setattr__를 우회하도록 변경하였습니다. [해당 코드](allocation/adapter/orm.py)의 detour_value_object_frozen_setattr 함수 및 사용 시점(start_mappers 함수)를 확인할 수 있습니다.

## UOW의 경합 조건

[기존 UOW의 코드](https://github.com/cosmicpython/code/blob/master/src/allocation/service_layer/unit_of_work.py)는 단일 uow 객체를 활용하며, 동기적으로 동작한다는 가정 하에 \_\_enter__ 진입 시(with uow:) uow.session에 세션을 할당하는 방식으로 구성되어 있습니다.

여러 비동기 task에서 단일 uow 인스턴스의 \_\_aenter__에 진입함으로써 uow.session을 덮어쓰는 경합 조건이 발생하였습니다. 단일 uow 객체가 아닌 [uow_class](allocation/adapter/unit_of_work.py)를 사용해 매번 새로운 uow 인스턴스를 생성하는 방식으로 변경하였습니다.

또한, UOW가 구현 세부사항에 속한다고 판단하여 서비스 레이어에서 어뎁터 레이어로 이동하였습니다.

## 이벤트의 소유권

도메인 이벤트는 '어떠한 일이 발생함'에 대해 있어 기록되는 값 객체로 구현됩니다.

기존 코드에서 이벤트를 수집하는 방식은 다음과 같습니다.
1. Aggregate 인스턴스가 자신 내부에서 발생한 이벤트를 events 속성으로 수집
2. Repository가 seen 속성으로 get 또는 add 된 인스턴스를 보유
3. uow가 collect_new_events 메서드로 자신의 repository 속성으로 접근하여 events를 수집
4. messagebus가 자신의 uow 인스턴스를 통해 이벤트를 수집하여 실행

문제점은 다음과 같습니다.
- messagebus - uow - repository - aggregate를 거치는 일련의 과정이 서로 결합되어 있습니다.
- 개념 상 event는 서비스 레이어의 관점이며 도메인 객체와 무관합니다. Aggregate가 events 속성을 지닐 이유가 없습니다. 설령 같은 트랜잭션 내에서 영속화되어야 한다고 해도 마찬가지입니다. (outbox 패턴 참조)

해당 문제를 해결하기 위해 조사해 본 결과, [Buzzvil](https://www.buzzvil.com/ko/main)에서 발표한 [Async Cosmic Python 자료](https://speakerdeck.com/buzzvil/async-cosmic-python)를 찾을 수 있었습니다. 핵심 아이디어는 모듈 수준의 변수로 정의되어, 접근하는 Task마다 다른 값을 반환하는 [contextvars](https://docs.python.org/ko/3/library/contextvars.html#asyncio-support)를 활용하는 부분이었습니다.

해당 아이디어를 활용하여, 이벤트를 도메인 객체의 속성으로 관리하는 방식 대신 코드 컨텍스트(Context Manager) 수준의 관심사로 변경하였습니다. ([MessageCatcher](allocation/service/message_bus.py))

또한 Product 메서드에서 이벤트를 생성하는 과정을 모두 서비스 레이어로 이동하였습니다.

## MessageBus 종속성 주입

MessageBus는 커맨드 또는 이벤트(Message)를 받아 콜러블(Handler)의 첫번째 인자로 넘겨주고, 자신이 지닌 종속성을 기타 인자로 전달하는 중재자입니다. 기존의 코드는 MessageBus를 인스턴스화 하는 과정 내에 Handler를 Message 파라미터를 제외한 모든 종속성이 미리 주입된 콜러블로 변환되는 과정이 있었습니다. 핸들러 함수 형태를 inspect로 분석하고 인자의 이름으로 매핑하는 [방식](https://github.com/cosmicpython/code/blob/master/src/allocation/bootstrap.py)으로 작성되어 있습니다.

개인적으로 생각하기에, 어차피 함수에 정의된 이름으로 주입된 객체를 매핑할 것이라면 파이썬의 dictionary unpack 문법을 사용한 것과 다를 바 없다고 생각했습니다. 핸들러를 호출할 때 dictionary unpack 문법을 활용해 인자를 전달하는 방식을 선택했습니다.

문제점과 이에 대한 해결 방안을 설명합니다.
- 모든 Handler에 반드시 kwargs 파라미터(**...)가 있기를 요구한다(주입되었으나 사용되지 않을 종속성을 무시) => python의 [Callback Protocol](https://peps.python.org/pep-0544/#callback-protocols)을 활용하면 Callable의 인자 구조를 타이핑 기능으로 제한 가능([_Handler](allocation/service/message_bus.py) 프로토콜 참조)
- message_bus 객체 생성 시점에서 모든 종속성 객체들이 제공될 수 있음을 보장 => inspect로 handler들의 함수 인자(첫번째 Message 인자와 kwargs 인자를 제외한)와 message_bus가 지닌 deps 딕셔너리 매핑을 대조하는 것으로 해결 ([validate_deps](allocation/service/message_bus.py) 참조)

## [Outbox 패턴](https://microservices.io/patterns/data/transactional-outbox.html) 추가

Outbox는 에그리게잇의 변경과 그에 따른 이벤트 전달 사이에서 발생할 수 있는 불일치를 해결하기 위해 등장한 패턴입니다. 서버 다운이 발생했을 경우 전달되지 않은 이벤트가 소실될 수 있으며 어떻게 해결할 것인가 대한 문제입니다. 에그리게잇의 영속화 트랜잭션 내에서 이벤트 또한 영속화하여 저장하고, 메세지 브로커에게 전달 후 삭제한다는 것이 핵심 아이디어입니다.

RDBMS의 경우 Outbox 패턴은 Repository 패턴과 구조가 유사하며, Repository와 마찬가지로 [UOW](allocation/adapter/unit_of_work.py)에서 사용됩니다. 구현 세부사항은 [코드](allocation/adapter/outbox.py)에서 확인하실 수 있습니다.

이렇게 영속화 된 이벤트는 MSA 간 정보 전달에 사용될 메세지 브로커에 전달되어야 하며, 이를 "이벤트 릴레이 패턴"이라고 부릅니다. 두 가지 구현 패턴이 존재합니다.
- 폴링 게시자 패턴 : DB Outbox의 Event들을 읽어들여 직접 Message Broker에 송신 후 이벤트를 Outbox에서 제거
- 트랜잭션 로그 테일링 패턴 : Outbox 테이블의 트랜잭션 로그의 정보를 파싱하여 Message Broker에게 송신

결과적으로, 메세지 브로커를 Redis에서 Kafka로 변경하였으며, Kafka Connect를 활용해 트랜잭션 로그 테일링 패턴을 적용하였습니다. '최소한 한 번의 전송'을 보장하도록 설계되어 있어 여러 번 메세지가 재전송 될 수 있다는 점을 유의해야 합니다. 메세지를 소비하는 측에서 '단 한번의 처리'를 위해 [Inbox 패턴](https://event-driven.io/en/outbox_inbox_patterns_and_delivery_guarantees_explained/) 또는 멱등적 동작을 수행하는 핸들러를 사용하여야 합니다. 외부 서비스에서 발생한 이벤트로 결과적 일관성을 달성해야 하는 동작은 해당 서비스에 포함되어 있지 않기 때문에 구현하지 않았습니다.

## Return After Work

기존의 코드는 핸들러 처리 중 메세지가 발생하는 만큼의 모든 메세지를 처리한 이후에 동작하도록 구성되어 있습니다. 대략적인 전개는 다음과 같습니다.

1. C1 수행 중 E1, E2, E3 발생
2. E1, E2, E3를 순차적으로 처리
3. Response

Starlette 및 Fastapi에서 제공하는 기능 "BackgroundTask"를 활용하면 Response 반환 이후 수행될 작업을 지정할 수 있습니다. 이를 활용하여 다음과 같은 로직을 떠올렸습니다.

1. C1 수행 중 E1, E2, E3 발생
2. E1, E2, E3를 병렬적으로 처리(asyncio.gather)하는 로직을 지닌 Task 객체 생성
3. Response 이후 Task 객체 처리

2번 동작을 위해 기존 MessageBus의 동작을 변경하여, 직접적으로 요청된 작업과 트리거(issue된 동작들)되어 실행되어야 할 작업을 분리하였고, handle 수행 시 return_hooked_task를 True로 지정하는 것으로 후행 작업을 태스크 객체로 반환하도록 수정하였습니다. ([MessageBus의 handle 메서드 참조](allocation/service/message_bus.py))

재귀 동작(A1 수행 중 A2 발생, A2 발생 중 A1 발생...)이 발생할 경우 이를 중단할 방법이 구현되어 있지 않습니다. 비순환 구조로 변환해야 하는가에 대한 의문도 있었으나, 결론을 내지 못해 순환 구조의 발생을 막지 않았습니다. 개인적으로 이를 휴먼 에러로 보고 있습니다.

3번 동작을 위해 조사한 결과 Starlette 및 FastAPI의 BackgroundTask는 콜러블에 대해서만 구현되어 있었으며 Awaitable 객체는 지원하지 않았습니다. 코드를 살펴본 결과 단지 BackgroundTask에게 async \_\_call__ 특수 메서드를 요구할 뿐이었으며, 호출 시 self.awaitable을 await하는 [AwaitableBackgroundTask](allocation/entrypoint/fastapi_.py)를 정의하여 활용하였습니다.

Response After Work 동작은 [fastapi 엔드포인트 allocate](allocation/entrypoint/fastapi_.py)에서 사용되었습니다. JSONResponse의 인수 AwaitableBackgroundTask(task)를 확인하십시오.

## 기타 변경 사항

- docker-compose를 활용한 개발 환경 구축
- kafka connect, database 대기 및 스키마 초기화 모듈 추가
- sqlalchemy engine 2.0 스타일로 마이그레이션

## 미예정 사항

- alembic을 활용한 데이터베이스 스키마 관리
- CI / CD 파이프라인 구축