from fastapi import FastAPI
from api import seller_socket
from api import jobs
from api import users  

app = FastAPI()

app.include_router(seller_socket.router)
app.include_router(jobs.router)
app.include_router(users.router)
