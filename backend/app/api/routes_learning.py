from typing import Annotated

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.actions.schemas import ActionRead
from app.database.models import UserProfile
from app.database.session import get_db
from app.domains.learning import service
from app.domains.learning.schemas import (
    CourseCreate,
    CourseRead,
    CourseUpdate,
    ExamCreate,
    ExamRead,
    ExamUpdate,
    LearningCandidateRead,
    LearningContextRead,
    LearningStatusRead,
    LearningTrajectoryRead,
    StudySessionCreate,
    StudySessionRead,
    TopicCreate,
    TopicRead,
    TopicUpdate,
)

router = APIRouter(prefix="/learning", tags=["learning"])


@router.get("/status", response_model=LearningStatusRead)
def learning_status(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.status_summary(db, user)


@router.get("/context", response_model=LearningContextRead)
def learning_context(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.learning_context(db, user)


@router.post("/courses", response_model=CourseRead)
def create_course(payload: CourseCreate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    course = service.create_course(db, user, payload)
    db.commit()
    return course


@router.get("/courses", response_model=list[CourseRead])
def list_courses(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.list_courses(db, user)


@router.patch("/courses/{course_id}", response_model=CourseRead)
def update_course(course_id: str, payload: CourseUpdate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    course = service.update_course(db, user, course_id, payload)
    db.commit()
    return course


@router.post("/exams", response_model=ExamRead)
def create_exam_endpoint(payload: ExamCreate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    exam = service.create_exam(db, user, payload)
    service.sync_candidate_actions(db, user)
    response = service.exam_to_read(db, user, exam)
    db.commit()
    return response


@router.get("/exams", response_model=list[ExamRead])
def get_exams(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return [service.exam_to_read(db, user, exam) for exam in service.list_exams(db, user)]


@router.get("/exams/{exam_id}", response_model=ExamRead)
def get_exam(exam_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.exam_to_read(db, user, service._get_exam(db, user, exam_id))


@router.patch("/exams/{exam_id}", response_model=ExamRead)
def update_exam(exam_id: str, payload: ExamUpdate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    exam = service.update_exam(db, user, exam_id, payload)
    service.sync_candidate_actions(db, user)
    response = service.exam_to_read(db, user, exam)
    db.commit()
    return response


@router.get("/exams/{exam_id}/trajectory", response_model=LearningTrajectoryRead)
def get_exam_trajectory(exam_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.trajectory_for_exam(db, user, service._get_exam(db, user, exam_id))


@router.post("/exams/{exam_id}/topics", response_model=TopicRead)
def create_topic(exam_id: str, payload: TopicCreate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    topic = service.create_topic(db, user, exam_id, payload)
    service.sync_candidate_actions(db, user)
    db.commit()
    return topic


@router.get("/exams/{exam_id}/topics", response_model=list[TopicRead])
def list_topics(exam_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.list_topics(db, user, exam_id)


@router.patch("/topics/{topic_id}", response_model=TopicRead)
def update_topic(topic_id: str, payload: TopicUpdate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    topic = service.update_topic(db, user, topic_id, payload)
    service.sync_candidate_actions(db, user)
    db.commit()
    return topic


@router.post("/study-sessions", response_model=StudySessionRead)
def log_study_session(
    payload: StudySessionCreate,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    session = service.log_study_session(db, user, payload, idempotency_key=idempotency_key)
    service.sync_candidate_actions(db, user)
    db.commit()
    return session


@router.get("/study-sessions", response_model=list[StudySessionRead])
def list_study_sessions(exam_id: str | None = None, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.list_study_sessions(db, user, exam_id=exam_id)


@router.get("/candidates", response_model=list[LearningCandidateRead])
def learning_candidates(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.learning_candidates(db, user)


@router.post("/candidates/sync-actions", response_model=list[ActionRead])
def sync_learning_candidate_actions(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    actions = service.sync_candidate_actions(db, user)
    response = [ActionRead.model_validate(action).model_copy(update={"world_revision": user.world_revision}) for action in actions]
    db.commit()
    return response
