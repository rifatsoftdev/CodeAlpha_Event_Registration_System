import uvicorn
import socket


def get_ip():
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        if s is not None:
            s.close()
    return ip


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=get_ip(),
        port=3000,
        reload=True,
        log_level="info"
    ) 

# uvicorn app.main:app --reload
