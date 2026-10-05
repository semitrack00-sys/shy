import os
import httpx

BASE=os.getenv("SHY_API_BASE_URL","http://127.0.0.1:8031").rstrip("/")
T=60.0

def a(c,m):
    if not c:
        raise AssertionError(m)

h=httpx.get(BASE+"/health",timeout=T)
a(h.status_code==200,h.text)
p=h.json()
a(p.get("version")=="0.31.0",p)
a(p.get("application_healthy") is True,"runtime health")
tc=p.get("temporal_capabilities") or {}
a(tc.get("timezone_aware_planning") is True,tc)
a(tc.get("external_schedule_creation") is False,tc)
print("v0.31 live health: PASS")

plan=httpx.post(BASE+"/temporal/plan",json={
    "tasks":[
        {"task_id":"load","duration_minutes":30,"earliest_start":"2026-10-05T08:00:00-07:00","deadline":"2026-10-05T09:00:00-07:00","dependencies":[]},
        {"task_id":"deliver","duration_minutes":60,"earliest_start":"2026-10-05T08:15:00-07:00","deadline":"2026-10-05T11:00:00-07:00","dependencies":["load"]}
    ],
    "max_tasks":32
},timeout=T)
a(plan.status_code==200,plan.text)
body=plan.json()
temporal=body.get("temporal") or {}
a(temporal.get("boundary")=="READY",temporal)
a(temporal.get("tasks")[1]["start"]=="2026-10-05T08:30:00-07:00",temporal)
a(body.get("external_schedule_created") is False,body)
print("live feasible temporal plan: PASS")

naive=httpx.post(BASE+"/temporal/plan",json={
    "tasks":[
        {"task_id":"x","duration_minutes":30,"earliest_start":"2026-10-05T08:00:00","deadline":"2026-10-05T09:00:00","dependencies":[]}
    ]
},timeout=T)
a(naive.status_code==200,naive.text)
a((naive.json().get("temporal") or {}).get("boundary")=="TIMEZONE_REQUIRED",naive.json())
print("live timezone boundary: PASS")

late=httpx.post(BASE+"/temporal/plan",json={
    "tasks":[
        {"task_id":"late","duration_minutes":90,"earliest_start":"2026-10-05T08:00:00+00:00","deadline":"2026-10-05T09:00:00+00:00","dependencies":[]}
    ]
},timeout=T)
a(late.status_code==200,late.text)
a((late.json().get("temporal") or {}).get("boundary")=="DEADLINE_CONFLICT",late.json())
print("live deadline conflict: PASS")

rec=httpx.post(BASE+"/temporal/recurrence-preview",json={
    "start":"2026-10-05T08:00:00+00:00",
    "every_minutes":60,
    "occurrences":30,
    "max_occurrences":20
},timeout=T)
a(rec.status_code==200,rec.text)
rp=rec.json()
a(len(rp.get("occurrences") or [])==20,rp)
a(rp.get("bounded") is False,rp)
a(rp.get("external_schedule_created") is False,rp)
print("live recurrence bound: PASS")

print("SHY v0.31 TEMPORAL INTELLIGENCE LIVE GATE: PASS")
