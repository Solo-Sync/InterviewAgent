from scoring_engine.evaluator import Evaluator
from scoring_engine.aggregator import Aggregator
from scoring_engine.report_generator import ReportGenerator

def main():
    evaluator = Evaluator()
    raw_scores = evaluator.evaluate(...)
    
    aggregator = Aggregator()
    aggregated = aggregator.aggregate(raw_scores)
    
    report = ReportGenerator.generate_report(
        aggregated_score=aggregated['score'],
        confidence=aggregated['confidence'],
        deductions=aggregated['deductions'],
        evidences=aggregated['evidences']
    )
    print(report)

if __name__ == "__main__":
    main()