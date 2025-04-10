import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from main import app, load_users, save_users, load_todos, save_todos, User, TodoItem

client = TestClient(app)

USER_DATA_FILE = "user_data.json"
TODO_DATA_FILE = "todo_data.json"


@pytest.fixture(autouse=True)
def cleanup_files():
    """
    각 테스트 시작 전/후로 user_data.json, todo_data.json 파일을 초기화합니다.
    """
    # 테스트 전
    if os.path.exists(USER_DATA_FILE):
        os.remove(USER_DATA_FILE)
    if os.path.exists(TODO_DATA_FILE):
        os.remove(TODO_DATA_FILE)

    yield  # 여기까지 실행 후 테스트 수행

    # 테스트 후
    if os.path.exists(USER_DATA_FILE):
        os.remove(USER_DATA_FILE)
    if os.path.exists(TODO_DATA_FILE):
        os.remove(TODO_DATA_FILE)


def test_root_redirect_to_login():
    """
    GET / 요청 시 /login으로 리다이렉트되는지 확인
    """
    response = client.get("/")
    # FastAPI의 RedirectResponse는 궁극적으로 HTML 렌더링을 반환하므로 status_code는 200이 될 수 있음.
    # 실제로는 303/307로 리다이렉트가 처리된 뒤 최종 응답은 200(로그인 페이지)일 수 있음.
    assert response.status_code == 200
    assert "로그인" in response.text


def test_register_and_login():
    """
    회원가입 -> 로그인 과정을 테스트
    """
    # 1) 회원가입 폼 페이지 확인
    response = client.get("/register")
    assert response.status_code == 200
    assert "회원가입" in response.text

    # 2) 회원가입 진행
    response = client.post(
        "/register",
        data={"username": "testuser", "password": "testpass", "email": "test@example.com"},
        follow_redirects=False
    )
    # 회원가입 성공 시 /login 으로 리다이렉트(303)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"

    # 3) 중복 회원가입 시도
    response = client.post(
        "/register",
        data={"username": "testuser", "password": "testpass", "email": "test@example.com"},
        follow_redirects=True
    )
    # 이미 존재하는 사용자명 -> 에러메시지
    assert response.status_code == 200
    assert "이미 존재하는 username" in response.text

    # 4) 로그인 페이지
    response = client.get("/login")
    assert response.status_code == 200
    assert "로그인" in response.text

    # 5) 로그인 시도(성공)
    response = client.post(
        "/login",
        data={"username": "testuser", "password": "testpass"},
        follow_redirects=False
    )
    # 성공 시 /index 로 리다이렉트(303)
    assert response.status_code == 303
    assert response.headers["location"] == "/index"

    # 6) 세션이 유지된 상태로 /index 접근
    response = client.get("/index", follow_redirects=False)
    assert response.status_code == 200
    assert "할 일 목록" in response.text or "Todo" in response.text


def test_login_fail():
    """
    존재하지 않는 계정으로 로그인 시도 -> 로그인 실패 테스트
    """
    response = client.post(
        "/login",
        data={"username": "wronguser", "password": "wrongpass"},
        follow_redirects=False
    )
    # 로그인 실패 시 다시 로그인 페이지(200) + 에러메시지
    assert response.status_code == 200
    assert "아이디 또는 비밀번호가 틀렸습니다." in response.text


def test_todo_crud_flow():
    """
    Todo CRUD 테스트
    1) 회원가입 및 로그인
    2) Todo 생성
    3) Todo 상세보기
    4) Todo 수정
    5) Todo 삭제
    """
    # ------------------
    # 1) 회원가입 및 로그인
    # ------------------
    client.post(
        "/register",
        data={"username": "tester", "password": "pass", "email": "test@example.com"},
        follow_redirects=False
    )
    client.post(
        "/login",
        data={"username": "tester", "password": "pass"},
        follow_redirects=False
    )

    # ------------------
    # 2) Todo 생성
    # ------------------
    create_response = client.post(
        "/create",
        data={"title": "Test Title", "description": "Test Description"},
        follow_redirects=False
    )
    # 생성 후 /index로 리다이렉트
    assert create_response.status_code == 303
    assert create_response.headers["location"] == "/index"

    # 저장된 Todo 확인
    todos = load_todos()
    assert len(todos) == 1
    todo_item = todos[0]
    assert todo_item.title == "Test Title"
    assert todo_item.description == "Test Description"
    assert todo_item.completed is False

    # ------------------
    # 3) Todo 상세보기
    # ------------------
    detail_response = client.get(f"/todos/{todo_item.id}")
    assert detail_response.status_code == 200
    assert "Test Title" in detail_response.text
    assert "Test Description" in detail_response.text

    # ------------------
    # 4) Todo 수정
    # ------------------
    update_response = client.post(
        f"/update/{todo_item.id}",
        data={"title": "Updated Title", "description": "Updated Desc", "completed": "true"},
        follow_redirects=False
    )
    assert update_response.status_code == 303

    updated_todos = load_todos()
    assert updated_todos[0].title == "Updated Title"
    assert updated_todos[0].description == "Updated Desc"
    assert updated_todos[0].completed is True

    # ------------------
    # 5) Todo 삭제
    # ------------------
    delete_response = client.post(f"/delete/{todo_item.id}", follow_redirects=False)
    assert delete_response.status_code == 303

    after_delete = load_todos()
    assert len(after_delete) == 0


def test_logout():
    """
    로그아웃 테스트
    1) 로그인 후 로그아웃
    2) 로그아웃 상태에서 /index 접근 시도 -> 401
    """
    # 회원가입/로그인
    client.post(
        "/register",
        data={"username": "tester", "password": "pass", "email": "test@example.com"},
        follow_redirects=False
    )
    client.post(
        "/login",
        data={"username": "tester", "password": "pass"},
        follow_redirects=False
    )

    # /index 접근(로그인 상태)
    response_index = client.get("/index")
    assert response_index.status_code == 200

    # 로그아웃
    response_logout = client.get("/logout", follow_redirects=False)
    assert response_logout.status_code == 303
    assert response_logout.headers["location"] == "/login"

    # 로그아웃 후 /index 접근 -> 401
    response_index_after_logout = client.get("/index")
    assert response_index_after_logout.status_code == 401
    assert "로그인이 필요합니다." in response_index_after_logout.text
