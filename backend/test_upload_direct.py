"""Прямой тест загрузки файла через API с авторизацией Yandex OAuth."""
import requests
import json
from pathlib import Path

API_URL = "http://127.0.0.1:8000"
TEST_FILE = Path("../testsss/КП АНЕП.docx")

def main():
    print("=" * 80)
    print("ТЕСТ ЗАГРУЗКИ ФАЙЛА ЧЕРЕЗ API (Yandex OAuth)")
    print("=" * 80)
    
    # 1. Авторизация через Yandex OAuth (используем edwatik)
    print("\n1. Авторизация через Yandex OAuth...")
    
    # Симулируем OAuth токен (обычно приходит с фронтенда)
    oauth_payload = {
        "access_token": "dummy_token_for_test",
        "email": "edwatik@yandex.ru",
        "first_name": "Eduard",
        "last_name": "Watike"
    }
    
    # Попробуем напрямую создать JWT токен для тестирования
    # Используем существующую функцию создания токена
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from app.utils.auth import create_access_token
    
    # Создаем токен напрямую для пользователя edwatik (id=6 из browser audit)
    token = create_access_token(data={
        "sub": "edwatik",
        "id": 6,
        "username": "edwatik",
        "email": "edwatik@yandex.ru",
        "role": "moderator"
    })
    
    print(f"✅ Токен создан: ...{token[-10:]}")
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    # 2. Создаем заявку
    print("\n2. Создание заявки...")
    create_resp = requests.post(
        f"{API_URL}/cabinet/requests",
        headers=headers,
        json={"title": "Тест обновленного промпта Groq"}
    )
    
    if create_resp.status_code != 200:
        print(f"❌ Ошибка создания заявки: {create_resp.status_code}")
        print(create_resp.text)
        return
    
    request_id = create_resp.json().get("id")
    print(f"✅ Заявка создана: ID {request_id}")
    
    # 3. Загружаем файл для распознавания
    print("\n3. Загрузка и распознавание файла...")
    
    if not TEST_FILE.exists():
        print(f"❌ Файл не найден: {TEST_FILE}")
        return
    
    with open(TEST_FILE, "rb") as f:
        files = {
            "file": (TEST_FILE.name, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        }
        
        upload_resp = requests.post(
            f"{API_URL}/cabinet/requests/{request_id}/positions/upload",
            headers=headers,
            files=files,
            params={"engine": "auto"}
        )
    
    if upload_resp.status_code != 200:
        print(f"❌ Ошибка загрузки: {upload_resp.status_code}")
        print(upload_resp.text[:500])
        return
    
    print(f"✅ Файл загружен и распознан")
    
    # 4. Проверяем результат
    result = upload_resp.json()
    positions = result.get("raw_keys_json", [])
    
    # Проверяем заголовки с usage
    groq_usage = {}
    for key in ["x-groq-prompt-tokens", "x-groq-completion-tokens", "x-groq-total-tokens", "x-groq-total-time"]:
        if key in upload_resp.headers:
            groq_usage[key] = upload_resp.headers[key]
    
    print(f"\n{'=' * 80}")
    print("РЕЗУЛЬТАТ РАСПОЗНАВАНИЯ С ОБНОВЛЕННЫМ ПРОМПТОМ")
    print(f"{'=' * 80}")
    
    if groq_usage:
        print("\n🤖 Groq Usage:")
        print(f"  - Prompt tokens: {groq_usage.get('x-groq-prompt-tokens', 'N/A')}")
        print(f"  - Completion tokens: {groq_usage.get('x-groq-completion-tokens', 'N/A')}")
        print(f"  - Total tokens: {groq_usage.get('x-groq-total-tokens', 'N/A')}")
        print(f"  - Time: {groq_usage.get('x-groq-total-time', 'N/A')}s")
    
    print(f"\n📦 Позиции найдено: {len(positions)}")
    
    if positions:
        print("\nРаспознанные позиции:")
        for i, pos in enumerate(positions, 1):
            print(f"  {i}. {pos}")
    
    # Проверяем желаемый формат
    print(f"\n{'=' * 80}")
    print("ПРОВЕРКА ФОРМАТА")
    print(f"{'=' * 80}")
    
    desired = [
        "Труба жесткая термостойкая",
        "Труба разборная гладкая",
        "Труба гофрированная двустенная",
        "Заглушка"
    ]
    
    matches = []
    for des in desired:
        found = False
        for pos in positions:
            if pos.startswith(des) or des in pos:
                matches.append(f"✅ '{des}' → '{pos}'")
                found = True
                break
        if not found:
            matches.append(f"❌ '{des}' → не найдено")
    
    for m in matches:
        print(f"  {m}")
    
    success_count = sum(1 for m in matches if m.startswith("✅"))
    
    print(f"\n{'=' * 80}")
    if success_count == len(desired):
        print("🎉 ВСЕ ПОЗИЦИИ СООТВЕТСТВУЮТ ЖЕЛАЕМОМУ ФОРМАТУ!")
    elif success_count > 0:
        print(f"⚠️  Частичное соответствие: {success_count}/{len(desired)}")
    else:
        print("❌ Позиции не соответствуют ожиданиям")
    print(f"{'=' * 80}")

if __name__ == "__main__":
    main()
