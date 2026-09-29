def test_home_redirects_to_savedeal(client):
    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/savedeal")


def test_sidebar_home_links_to_command_center(client):
    body = client.get("/savedeal").get_data(as_text=True)

    assert 'href="http://localhost:5000"' in body


def test_savedeal_page_renders_operations_dashboard(client):
    response = client.get("/savedeal")

    assert response.status_code == 200
    body = response.get_data(as_text=True)

    assert "예약판매 이탈 방지" in body
    assert 'class="summary-grid"' in body
    assert 'id="reservation-rows"' in body
    assert 'id="detail-panel"' in body
    for label in ["전체", "처리 필요", "고위험", "오늘 마감", "완료"]:
        assert label in body
    assert 'data-filter="due_today"' in body
    assert "js/dashboard.js" in body
    assert 'href="/savedeal/new"' in body


def test_savedeal_new_page_renders_input_and_result_panels(client):
    response = client.get("/savedeal/new")

    assert response.status_code == 200
    body = response.get_data(as_text=True)

    assert "신규 예약 등록" in body
    assert 'id="precheck-form"' in body
    assert 'id="customer_id"' in body
    assert 'id="store_id"' in body
    assert 'id="device_model"' in body
    assert 'id="desired_activation_date"' in body
    assert 'id="result-content"' in body
    assert 'id="register-button"' in body
    assert "고객번호 C001" in body
    assert "js/precheck.js" in body
