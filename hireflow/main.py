"""Run the whole HireFlow pipeline:  python main.py"""
from hireflow.agents.coordinator import PipelineCoordinator


def main() -> None:
    pool = PipelineCoordinator().run()
    print(pool.final_report)
    if pool.bias_report:
        print("\nBias Guard flagged:", [b["cid"] for b in pool.bias_report])
    print(f"\nRun log appended to logs/run_log.txt (run id {pool.log.run_id})")


if __name__ == "__main__":
    main()
