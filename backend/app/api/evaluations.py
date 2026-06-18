import asyncio
import json
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..core.jobs import Job, create_job, get_job
from ..core.security import get_current_user
from ..db import models
from ..db.database import SessionLocal, get_db
from ..pipeline import agent_model as ag_model
from ..pipeline import agent_dataset as ag_dataset
from ..pipeline import agent_analyzer, predictor, report_agent
from ..pipeline.analyzer import analyze as enrich
from ..pipeline.features import auc_to_risk
from ..schemas.evaluation import (
    EvaluateInput,
    EvaluateResponse,
    EvaluationRecord,
    SubmitResponse,
)

router = APIRouter(tags=["evaluations"])

_DEFAULTS: Dict[str, Any] = {
    "model_type":                  "CNN",
    "dataset_modality":            "tabular",
    "depth":                       6,
    "num_heads":                   0,
    "embed_dim":                   0,
    "mlp_ratio":                   0.0,
    "nb_params":                   100_000,
    "patch_size":                  0,
    "epochs":                      50,
    "learning_rate":               0.001,
    "batch_size":                  64,
    "dropout":                     0.0,
    "weight_decay":                0.0,
    "data_augmentation":           False,
    "nb_train_samples":            10_000,
    "nb_classes":                  2,
    "dataset_intra_variance":      0.5,
    "dataset_inter_class_distance": 0.5,
    "train_accuracy":              0.9,
    "test_accuracy":               0.85,
}


# ── Legacy manual-form endpoint ───────────────────────────────────────────────

@router.post("/evaluate", response_model=EvaluateResponse)
def evaluate(
    body: EvaluateInput,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    input_dict = body.model_dump()
    enriched = enrich(input_dict)
    auc = round(predictor.predict(enriched), 3)
    risk_level = auc_to_risk(auc)
    recommendations = report_agent.generate_recommendations(input_dict, auc, risk_level)
    report_text = report_agent.generate_report(input_dict, auc, risk_level)
    _save_evaluation(db, current_user.id, body, auc, risk_level, recommendations, report_text)
    return EvaluateResponse(
        auc=auc, risk_level=risk_level,
        recommendations=recommendations, report=report_text,
    )


# ── File-upload submit endpoint ───────────────────────────────────────────────

@router.post("/evaluate/submit", response_model=SubmitResponse)
async def submit_evaluation(
    background_tasks: BackgroundTasks,
    model_file:    Optional[UploadFile] = File(None),
    config_file:   Optional[UploadFile] = File(None),
    dataset_file:  Optional[UploadFile] = File(None),
    dataset_url:   Optional[str]        = Form(None),
    manual_params: str                  = Form("{}"),
    current_user:  models.User          = Depends(get_current_user),
):
    model_bytes    = await model_file.read()   if model_file   else None
    model_filename = model_file.filename or "" if model_file   else ""
    config_bytes   = await config_file.read()  if config_file  else None
    dataset_bytes  = await dataset_file.read() if dataset_file else None
    dataset_filename = dataset_file.filename or "" if dataset_file else ""

    try:
        manual = json.loads(manual_params)
    except Exception:
        manual = {}

    model_name   = model_filename or "modèle inconnu"
    dataset_name = dataset_filename or dataset_url or ""
    has_dataset  = bool(dataset_bytes or dataset_url)

    job = create_job()
    background_tasks.add_task(
        _run_pipeline,
        job=job,
        model_bytes=model_bytes,
        model_filename=model_filename,
        config_bytes=config_bytes,
        dataset_bytes=dataset_bytes,
        dataset_filename=dataset_filename,
        dataset_url=dataset_url,
        has_dataset=has_dataset,
        manual_params=manual,
        user_id=current_user.id,
        model_name=model_name,
        dataset_name=dataset_name,
    )
    return SubmitResponse(job_id=job.id)


# ── SSE stream endpoint ───────────────────────────────────────────────────────

@router.get("/evaluate/{job_id}/stream")
async def stream_job(
    job_id: str,
    current_user: models.User = Depends(get_current_user),
):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job introuvable.")

    async def generate():
        async for event in job.event_stream():
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── Evaluations history ───────────────────────────────────────────────────────

@router.get("/evaluations", response_model=List[EvaluationRecord])
def get_evaluations(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    evals = (
        db.query(models.Evaluation)
        .filter(models.Evaluation.user_id == current_user.id)
        .order_by(models.Evaluation.created_at.desc())
        .all()
    )
    result: List[EvaluationRecord] = []
    for e in evals:
        recs = json.loads(e.recommendations) if e.recommendations else []
        report_content = e.report.content if e.report else ""
        result.append(
            EvaluationRecord(
                id=e.id,
                created_at=e.created_at,
                auc=e.auc,
                risk_level=e.risk_level,
                recommendations=recs,
                report=report_content,
                model_name=e.model_name,
                dataset_name=e.dataset_name,
                input=EvaluateInput(
                    model_type=e.model_type,
                    dataset_modality=e.dataset_modality,
                    depth=e.depth or 6,
                    num_heads=e.num_heads or 0,
                    embed_dim=e.embed_dim or 0,
                    mlp_ratio=e.mlp_ratio or 0.0,
                    nb_params=e.nb_params or 100_000,
                    patch_size=e.patch_size or 0,
                    epochs=e.epochs or 50,
                    learning_rate=e.learning_rate or 0.001,
                    batch_size=e.batch_size or 64,
                    dropout=e.dropout or 0.0,
                    weight_decay=e.weight_decay or 0.0,
                    data_augmentation=e.data_augmentation or False,
                    nb_train_samples=e.nb_train_samples or 10_000,
                    nb_classes=e.nb_classes or 2,
                    dataset_intra_variance=e.dataset_intra_variance or 0.5,
                    dataset_inter_class_distance=e.dataset_inter_class_distance or 0.5,
                    train_accuracy=e.train_accuracy or 0.9,
                    test_accuracy=e.test_accuracy or 0.85,
                ),
            )
        )
    return result


# ── Pipeline (background task) ────────────────────────────────────────────────

async def _run_pipeline(
    job:              Job,
    model_bytes:      Optional[bytes],
    model_filename:   str,
    config_bytes:     Optional[bytes],
    dataset_bytes:    Optional[bytes],
    dataset_filename: str,
    dataset_url:      Optional[str],
    has_dataset:      bool,
    manual_params:    dict,
    user_id:          str,
    model_name:       str,
    dataset_name:     str,
) -> None:
    loop = asyncio.get_event_loop()
    features: Dict[str, Any] = dict(_DEFAULTS)

    # ── Step 1 : Agent Modèle ────────────────────────────────────────────────
    await job.push({"step": "agent_model", "status": "running",
                    "message": "Analyse du fichier modèle…"})
    try:
        def _run_model_agent():
            result = {}
            if model_bytes:
                try:
                    result.update(ag_model.analyze_pkl(model_bytes, model_filename))
                except Exception:
                    pass
            if config_bytes:
                try:
                    result.update(ag_model.analyze_config(config_bytes))
                except Exception:
                    pass
            return result

        model_features = await loop.run_in_executor(None, _run_model_agent)
        features.update(model_features)
        msg = ag_model.summary_message(model_features) if model_features else "Paramètres par défaut utilisés."
        await job.push({"step": "agent_model", "status": "done", "message": msg})
    except Exception as exc:
        await job.fail(f"Agent Modèle : {exc}")
        return

    # ── Step 2 : Agent Dataset (optionnel) ───────────────────────────────────
    if has_dataset:
        await job.push({"step": "agent_dataset", "status": "running",
                        "message": "Analyse du dataset…"})
        try:
            dataset_features = await loop.run_in_executor(
                None,
                ag_dataset.analyze,
                dataset_bytes, dataset_filename, dataset_url,
            )
            features.update(dataset_features)
            msg = ag_dataset.summary_message(dataset_features) if dataset_features \
                else "Dataset non lisible — valeurs par défaut utilisées."
            await job.push({"step": "agent_dataset", "status": "done", "message": msg})
        except Exception as exc:
            await job.fail(f"Agent Dataset : {exc}")
            return

    # Apply manual params (highest priority)
    for k, v in manual_params.items():
        if v is not None and v != "":
            features[k] = v

    agent_analyzer._coerce(features)

    # ── Step 3 : Predictor ───────────────────────────────────────────────────
    await job.push({"step": "predictor", "status": "running",
                    "message": "Prédiction de la vulnérabilité MIA…"})
    try:
        enriched   = enrich(features)
        auc        = round(await loop.run_in_executor(None, predictor.predict, enriched), 3)
        risk_level = auc_to_risk(auc)
        await job.push({"step": "predictor", "status": "done",
                        "message": f"AUC estimée : {auc:.3f} — Risque {risk_level}"})
    except Exception as exc:
        await job.fail(f"Predictor : {exc}")
        return

    # ── Step 4 : Reporter ────────────────────────────────────────────────────
    await job.push({"step": "reporter", "status": "running",
                    "message": "Génération du rapport et des recommandations…"})
    try:
        recommendations = report_agent.generate_recommendations(features, auc, risk_level)
        report_text     = report_agent.generate_report(features, auc, risk_level)
        await job.push({"step": "reporter", "status": "done",
                        "message": "Rapport généré avec succès."})
    except Exception as exc:
        await job.fail(f"Reporter : {exc}")
        return

    # ── Persist ──────────────────────────────────────────────────────────────
    try:
        db         = SessionLocal()
        input_obj  = EvaluateInput(**{k: features.get(k, _DEFAULTS.get(k)) for k in EvaluateInput.model_fields})
        _save_evaluation(db, user_id, input_obj, auc, risk_level,
                         recommendations, report_text,
                         model_name=model_name, dataset_name=dataset_name)
        db.close()
    except Exception:
        pass

    await job.finish({
        "auc":             auc,
        "risk_level":      risk_level,
        "recommendations": recommendations,
        "report":          report_text,
        "model_name":      model_name,
        "dataset_name":    dataset_name,
    })


def _save_evaluation(
    db:            Session,
    user_id:       str,
    body:          EvaluateInput,
    auc:           float,
    risk_level:    str,
    recommendations: list,
    report_text:   str,
    model_name:    str = "",
    dataset_name:  str = "",
) -> None:
    eval_record = models.Evaluation(
        id=str(uuid.uuid4()),
        user_id=user_id,
        model_type=body.model_type,
        dataset_modality=body.dataset_modality,
        depth=body.depth,
        num_heads=body.num_heads,
        embed_dim=body.embed_dim,
        mlp_ratio=body.mlp_ratio,
        nb_params=body.nb_params,
        patch_size=body.patch_size,
        epochs=body.epochs,
        learning_rate=body.learning_rate,
        batch_size=body.batch_size,
        dropout=body.dropout,
        weight_decay=body.weight_decay,
        data_augmentation=body.data_augmentation,
        nb_train_samples=body.nb_train_samples,
        nb_classes=body.nb_classes,
        dataset_intra_variance=body.dataset_intra_variance,
        dataset_inter_class_distance=body.dataset_inter_class_distance,
        train_accuracy=body.train_accuracy,
        test_accuracy=body.test_accuracy,
        auc=auc,
        risk_level=risk_level,
        recommendations=json.dumps(recommendations, ensure_ascii=False),
        model_name=model_name,
        dataset_name=dataset_name,
    )
    db.add(eval_record)
    db.flush()
    db.add(models.Report(
        id=str(uuid.uuid4()),
        evaluation_id=eval_record.id,
        content=report_text,
    ))
    db.commit()
