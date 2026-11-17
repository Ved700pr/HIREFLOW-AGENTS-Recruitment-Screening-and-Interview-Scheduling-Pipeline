"""Pipeline Coordinator - runs the stages in order and passes the SAME shared pool through each one.

    Parser -> Matcher -> Ranker -> Bias Guard -> Scheduler
"""
from hireflow import config
from hireflow.agents.base import BaseAgent
from hireflow.agents.bias_guard_agent import BiasGuardAgent
from hireflow.agents.matcher_agent import MatcherAgent
from hireflow.agents.parser_agent import ParserAgent
from hireflow.agents.ranker_agent import RankerAgent
from hireflow.agents.scheduler_agent import SchedulerAgent
from hireflow.shared_state import Candidate, CandidatePool, RunLog
from hireflow.tools.coordinator_tools import (
    build_final_report,
    build_recruitment_report,
    load_job_description,
    load_resumes,
    parse_job_description,
    run_stage,
)


class PipelineCoordinator(BaseAgent):
    name = "coordinator"
    role = "Run each stage in order and hand the shared candidate pool to the next stage."
    tools = [load_job_description, parse_job_description, load_resumes, build_final_report, build_recruitment_report]

    def __init__(
        self,
        job_path=config.DATA_DIR / "job_description.txt",
        resumes_dir=config.DATA_DIR / "resumes",
        availability_path=config.DATA_DIR / "availability.json",
        top_n: int = config.TOP_N,
        min_score: float = config.MIN_SHORTLIST_SCORE,
        log_path=config.LOG_PATH,
        bias_guard: bool = True,
    ):
        super().__init__()
        self.job_path, self.resumes_dir, self.log_path = str(job_path), str(resumes_dir), log_path
        self.stages = [("parse", ParserAgent()), ("match", MatcherAgent()), ("rank", RankerAgent())]
        if bias_guard:
            self.stages.append(("bias_check", BiasGuardAgent()))
        self.stages.append(("schedule", SchedulerAgent(availability_path, top_n, min_score)))

    def run(self, job_text: str | None = None, resumes: list[dict] | None = None) -> CandidatePool:
        """Run the pipeline. With no arguments it reads the files in data/.
        The frontend passes job_text and resumes ([{'id':..., 'text':...}]) directly."""
        log = RunLog(self.log_path)
        self.log = log
        if job_text is not None:
            job = self.call("parse_job_description", text=job_text)
        else:
            job = self.call("load_job_description", path=self.job_path)
        if resumes is None:
            resumes = list(self.call("load_resumes", folder=self.resumes_dir))
        pool = CandidatePool(job, log)
        for item in resumes:
            cid, n = str(item["id"]), 1
            while cid in pool.candidates:   # two files with the same name must not overwrite each other
                n += 1
                cid = f"{item['id']}_{n}"
            pool.add(Candidate(cid=cid, raw_text=item["text"]))
        self.say("inputs_loaded", f"job '{job['title']}', {len(resumes)} resumes")

        for stage_name, agent in self.stages:
            run_stage(stage_name, lambda a=agent: a.run(pool), log)

        rows = [
            {"cid": c.cid, "name": c.name, "rank": c.rank, "score": c.score, "slot": c.slot or "",
             "status": c.status, "rationale": c.rationale}
            for c in pool.all()
        ]
        pool.final_report = self.call("build_final_report", rows=rows, title=job["title"])
        pool.report_md = self.call("build_recruitment_report", records=pool.records(), job=job)
        self.say("run_finished", f"{sum(c.status == 'scheduled' for c in pool.all())} interviews scheduled")
        return pool
