# Async Cosmic Python

[파이썬으로 살펴보는 아키텍처 패턴](https://book.naver.com/bookdb/book_detail.nhn?bid=20554246)의 코드를 비동기로 전환하는 과정에서 만난 문제점들과 이를 해결한 방법에 대해 서술합니다.

다음과 같은 사전 지식이 필요합니다.
- [파이썬으로 살펴보는 아키텍처 패턴](https://book.naver.com/bookdb/book_detail.nhn?bid=20554246)의 내용
    - DDD, 헥사고날 아키텍처
- 비동기

## DDD 객체 설계

DDD 개념의 값객체, 엔티티, 에그리게잇의 정의에 python의 dataclasses, metaclass 및 typing.dataclass_transform을 사용하였습니다.

[기존 도메인 객체](https://github.com/cosmicpython/code/blob/master/src/allocation/domain/model.py)의 코드와 [Base](allocation\domain\models\bases.py), 구현([order_line](allocation\domain\models\order_line.py), [batch](allocation\domain\models\batch.py), [product](allocation\domain\models\product.py))의 코드를 비교하실 수 있습니다.

## SQLAlchemy ORM Mapping

sqlalchemy에서 orm을 통해 인스턴스를 가져올 경우 _sa_instance_state를 객체에 지정하여 세션 내 객체의 상태 정보(임시, 보류, 영구, 삭제)를 저장합니다.

값 객체의 경우 dataclass의 frozen=True를 지정하였기 때문에 별도의 필드 추가가 금지되도록 설계되어 있어 예외가 발생합니다. orm 매핑 시 ValueObject의 \_\_setattr__를 수정하도록 변경하였습니다. [해당 코드](allocation\adapter\orm.py)의 detour_value_object_frozen_setattr 함수 및 사용 시점(start_mappers 함수)를 확인할 수 있습니다.

## UOW의 경합 조건

[기존 UOW의 코드](https://github.com/cosmicpython/code/blob/master/src/allocation/service_layer/unit_of_work.py)는 단일 uow 객체를 활용하며, 동기적으로 동작한다는 가정 하에 \_\_enter__ 진입 시(with uow:) uow.session에 세션을 할당하는 방식으로 구성되어 있습니다.

여러 비동기 task에서 단일 uow 인스턴스의 \_\_enter__에 진입함으로써 uow.session을 덮어쓰는 경합 조건이 발생하였습니다. 단일 uow 객체를 의존성 주입하는 것이 아닌 [uow_class](allocation\adapter\unit_of_work.py)를 주입하여 매번 새로운 uow 인스턴스를 생성해 사용하는 방식으로 변경하였습니다.

또한, UOW가 헥사고날 포트 및 어댑터 계층에 위치하는 것이 적절하다고 판단하였습니다. SQLAlchemy ORM + Postgres DB가 아닌 Motor ORM + Mongo DB의 트랜잭션을 사용하는 UOW 또한 구현할 수 있기 때문입니다.

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

해당 문제를 해결하기 위해 조사해 본 결과, [Buzzvil](https://www.buzzvil.com/ko/main)에서 발표한 [Async Cosmic Python 자료](https://speakerdeck.com/buzzvil/async-cosmic-python)를 찾을 수 있었습니다. 핵심 아이디어는 다음과 같습니다.

- 모듈 수준의 변수로 정의되어, 접근하는 Task마다 다른 값을 반환하는 [contextvars](https://docs.python.org/ko/3/library/contextvars.html#asyncio-support)를 활용

해당 아이디어를 활용하여, "어떤 일이 발생하였음을 기록하는 값 객체"인 이벤트는 도메인 객체의 속성에 추가되는 것이 아닌 코드 컨텍스트(Context Manager type) 수준의 관심사로 변경되었습니다. [message_bus](allocation\service\message_bus.py)의 MessageCatcher에 해당 로직이 구현되어 있습니다.

## MessageBus에서 종속성 주입

MessageBus는 커맨드 또는 이벤트(메세지)를 받아 콜러블(핸들러)의 첫번째 인자로 넘겨주고, 자신이 지닌 종속성을 기타 인자로 전달하는 중재자입니다. 

기존의 코드는 핸들러를 메세지 버스에 등록할 시점에서, 메세지를 제외한 모든 종속성이 미리 주입되어, 단일 메세지만을 주입받는 콜러블로 변환되는 과정이 있었습니다. 핸들러 함수 형태를 inspect로 분석하고 인자의 이름으로 매핑하는 방식으로 작성되어 있습니다. (기존 코드 [bootstrap.py](https://github.com/cosmicpython/code/blob/master/src/allocation/bootstrap.py) 참조)

그러나 개인적으로 생각하기에, 어차피 함수에 정의된 이름으로 객체를 매핑할 것이라면 파이썬의 unpack 문법을 사용한 것과 다를 바 없다고 생각했습니다. 핸들러를 호출할 때 dictionary unpack 문법을 활용해 인자를 전달하는 방식을 선택했습니다.

단점과 이에 대한 해결 방안을 설명합니다.
- message_bus 객체 생성 시점에서 모든 handler에 적절한 종속성이 주입될 것이라고 보장할 수 없다 => inspect로 handler들의 함수 인자와 message_bus가 지닌 종속성 객체 매핑의 이름을 대조하는 것으로 해결 가능
- 모든 Handler에 반드시 kwargs 파라미터(**...)가 있기를 요구함(주입되었으나 사용되지 않을 종속성을 무시) => python의 [Callback Protocol](https://peps.python.org/pep-0544/#callback-protocols)을 활용하면 [Callable의 인자 구조를 제한](allocation\service\message_bus.py) 타이핑 기능으로 제한 가능

## MessageBus와 Message, handler

기존의 코드에서는 Command와 Event를 구분하여 사용했습니다. "A라는 일을 하기 바람"에 대한 단일 처리 커맨드 로직, "A라는 일이 수행됨"에 대한 다중 처리 이벤트 로직으로 구분되었습니다. 그러나 개인적으로 MessageBus에서 이 둘을 구분할 필요가 없다고 판단했습니다. 위에서 서술하였듯 "메세지를 콜러블의 첫번째 인자로 넘겨주고, 기타 인자를 종속성으로 주입하는 중재자"로 생각하였습니다.

그리하여 기존 메세지 버스의 이벤트 및 커멘드를 기준으로 동작을 구분하는 방식 대신 등록된 핸들러가 1개 인지 N개인지에 따라 

## 이벤트 발행 방식
- 기존에는 에그리게잇이 모든 이벤트를 소유하는 방식으로 되어 UOW에서 해당 events를 수집하고 MessageBus까지 전달하는 방식으로 설계되어 있었음.
- 마음에 안듬. 전달 과정이 복잡할 뿐더러, 정말로 이벤트의 "어떤 일이 발생함"의 주체가 에그리게잇인가? 아니면 로직 상의 일인가?
- 로직 상의 일이라고 생각하기에 contextvars를 활용해 MessageCatcher를 만들고 issue된 이벤트를 수집하는 방식으로 변경.

!!!!! 그런데, 이렇게 되면 도메인이 어플리케이션 레이어에 의존하는 형태가 되어버린다. 이 종속성을 다시 해결할 방법은 없을까?
- 두번째 선택지 - 서비스 계층에서 이벤트 발행 이 부분을 활용하자. issue를 도메인 객체에서 제거하고 서비스 계층으로 옮기는 것이다.

## 아웃박스 패턴
- 기존에는 redis 사용함.
- 결과적 일관성을 위해 이벤트를 레포지토리에 저장하고 큐에 전송하는 방식이 필요함.
- 아웃박스 패턴을 적용하여 이벤트 영속화, CDC를 이용하여 기존 redis 방식 대신 트랜잭션 로그 테일링 도입

## 기타 수정사항
- docker-compose를 활용한 개발 환경 구축
- kafka connect, database 초기화 모듈 추가
- sqlalchemy engine 2.0 스타일 마이그레이션

bacgroudtask로 반환 후 적용 가능한지 확인해보자.