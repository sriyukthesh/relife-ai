import asyncio
import httpx

BASE = "http://127.0.0.1:8000"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzkzNzU5ODMxfQ.3-7wKEZv6MApMObzT3SBhI4dYO1lJLYn-JKXhnHXYLE"

async def main():
    headers = {"Authorization": f"Bearer {TOKEN}"}

    # Test /inspect with image
    print("=== Testing POST /inspect ===")
    with open(r"C:\Users\sri yukthesh\Downloads\secondlife-ai-phase1\test_components.jpg", "rb") as f:
        files = {"file": ("test.jpg", f, "image/jpeg")}
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                resp = await client.post(f"{BASE}/inspect", headers=headers, files=files)
                print(f"Status: {resp.status_code}")
                print(resp.json())
            except Exception as e:
                print(f"ERROR: {e}")

    # Test /teardown with image
    print("\n=== Testing POST /teardown ===")
    with open(r"C:\Users\sri yukthesh\Downloads\secondlife-ai-phase1\test_components.jpg", "rb") as f:
        files = {"file": ("test.jpg", f, "image/jpeg")}
        data = {"device_name": "test device"}
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                resp = await client.post(f"{BASE}/teardown", headers=headers, files=files, data=data)
                print(f"Status: {resp.status_code}")
                print(resp.json())
            except Exception as e:
                print(f"ERROR: {e}")

    # Test /builds/{id}/check-photo
    print("\n=== Testing POST /builds/1/check-photo ===")
    with open(r"C:\Users\sri yukthesh\Downloads\secondlife-ai-phase1\test_components.jpg", "rb") as f:
        files = {"file": ("test.jpg", f, "image/jpeg")}
        data = {"note": "Check LED polarity and resistor placement"}
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                resp = await client.post(f"{BASE}/builds/1/check-photo", headers=headers, files=files, data=data)
                print(f"Status: {resp.status_code}")
                print(resp.json())
            except Exception as e:
                print(f"ERROR: {e}")

asyncio.run(main())