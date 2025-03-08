from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel, EmailStr
from typing import List, Optional
import uuid
import secrets
from enum import Enum
from datetime import datetime

app = FastAPI()

users = {}
tasks = {}
subtasks = {}

def calculate_progress(task_id: uuid.UUID):
    task_subtasks = subtasks.get(task_id, [])
    if not task_subtasks:
        return 100 if tasks[task_id]['status'] == Status.COMPLETED else 0
    
    completed = sum(sub['progress_percentage'] for sub in task_subtasks)
    return (completed / len(task_subtasks))

class Status(str, Enum):
    COMPLETED = "COMPLETED"
    INCOMPLETE = "INCOMPLETE"
    PENDING = "PENDING"

class User(BaseModel):
    username: str
    name: str
    email: EmailStr
    session_token: str

class Task(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    status: Status
    sub_tasks_id: List[uuid.UUID] = []
    progress_percentage: int = 0
    priority: Optional[int] = 1

class SubTask(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    task_id: uuid.UUID
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    status: Status
    progress_percentage: int = 0
    priority: Optional[int] = 1

class CreateUserRequest(BaseModel):
    username: str
    name: str
    email: EmailStr

class CreateTaskRequest(BaseModel):
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: Optional[int] = 1

class CreateSubTaskRequest(BaseModel):
    task_id: uuid.UUID
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: Optional[int] = 1

class UpdateTaskRequest(BaseModel):
    task_id: uuid.UUID
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: Optional[int] = None

class UpdateSubTaskRequest(BaseModel):
    task_id: uuid.UUID
    subtask_id: uuid.UUID
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: Optional[int] = None

class StatusUpdateRequest(BaseModel):
    task_id: uuid.UUID
    subtask_id: Optional[uuid.UUID] = None
    status: Status

def authenticate_user(x_session_token: str = Header(...)):
    for user_id, user_data in users.items():
        if user_data["session_token"] == x_session_token:
            return user_id
    raise HTTPException(status_code=401, detail="Invalid session token")

@app.post("/users")
def create_user(user: CreateUserRequest):
    user_id = uuid.uuid4()
    session_token = secrets.token_hex(16)
    users[user_id] = {**user.dict(), "session_token": session_token}
    return {"user_id": user_id, "session_token": session_token, **users[user_id]}

@app.post("/tasks")
def create_task(task: CreateTaskRequest, user_id: uuid.UUID = Depends(authenticate_user)):
    task_id = uuid.uuid4()
    tasks[task_id] = {**task.dict(), "id": task_id, "user_id": user_id, "status": Status.PENDING, "progress_percentage": 0, "sub_tasks_id": []}
    return {"task_id": task_id, **tasks[task_id]}

@app.post("/tasks/{task_id}/subtasks")
def create_subtask(subtask: CreateSubTaskRequest, user_id: uuid.UUID = Depends(authenticate_user)):
    if subtask.task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    subtask_id = uuid.uuid4()
    subtask_obj = {**subtask.dict(), "id": subtask_id, "user_id": user_id, "status": Status.PENDING, "progress_percentage": 0}
    subtasks.setdefault(subtask.task_id, []).append(subtask_obj)
    tasks[subtask.task_id]['progress_percentage'] = calculate_progress(subtask.task_id)
    tasks[subtask.task_id]['status'] = Status.PENDING
    return {"subtask_id": subtask_id, **subtask_obj}

@app.get("/tasks")
def get_tasks(user_id: uuid.UUID = Depends(authenticate_user)):
    return {task_id: task for task_id, task in tasks.items() if task["user_id"] == user_id}

@app.get("/tasks/{task_id}")
def get_task(task_id: uuid.UUID, user_id: uuid.UUID = Depends(authenticate_user)):
    if task_id not in tasks or tasks[task_id]['user_id'] != user_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return {**tasks[task_id], "subtasks": subtasks.get(task_id, [])}

@app.patch("/tasks/{task_id}/status")
def update_task_status(task_id: uuid.UUID, update: StatusUpdateRequest, user_id: uuid.UUID = Depends(authenticate_user)):
    if task_id not in tasks or tasks[task_id]['user_id'] != user_id:
        raise HTTPException(status_code=404, detail="Task not found")
    tasks[task_id]['status'] = update.status
    if update.status == Status.COMPLETE:
        tasks[task_id]['progress_percentage'] = 100
        for sub in subtasks[task_id]:
            if update.status == Status.COMPLETE:
                sub['status'] = Status.COMPLETE
                sub['progress_percentage'] = 100
    return {"message": "Task status updated successfully"}

@app.patch("/tasks/{task_id}/subtasks/{subtask_id}/status")
def update_sub_task_status(task_id: uuid.UUID, subtask_id: uuid.UUID, update: StatusUpdateRequest, user_id: uuid.UUID = Depends(authenticate_user)):
    if task_id not in tasks or task_id not in subtasks or not any(sub['id'] == subtask_id for sub in subtasks[task_id]):
        raise HTTPException(status_code=404, detail="Task or Subtask not found")
    for sub in subtasks[task_id]:
        if sub['id'] == subtask_id:
            sub['status'] = update.status
            if update.status == Status.COMPLETE:
                sub['progress_percentage'] = 100
    tasks[task_id]['progress_percentage'] = calculate_progress(task_id)
    return {"message": "Subtask status updated successfully"}

@app.delete("/tasks/{task_id}")
def delete_task(task_id: uuid.UUID, user_id: uuid.UUID = Depends(authenticate_user)):
    if task_id not in tasks or tasks[task_id]['user_id'] != user_id:
        raise HTTPException(status_code=404, detail="Task not found")
    del tasks[task_id]
    subtasks.pop(task_id, None)
    return {"message": "Task deleted successfully"}
