from crewai import Crew

from agents.financial_advisor_agent import create_financial_advisor_agent
from agents.market_research_agent import create_market_research_agent
from agents.product_strategist_agent import create_product_strategist_agent
from agents.summary_agent import create_summary_agent

from tasks.market_research_task import create_market_research_task
from tasks.product_strategy_task import create_product_strategy_task
from tasks.financial_advisor_task import create_financial_advisor_task
from tasks.summary_task import create_summary_task

def build_startup_crew():

    market_agent = create_market_research_agent()
    product_agent = create_product_strategist_agent()
    financial_agent = create_financial_advisor_agent()
    summary_agent = create_summary_agent()

    market_research_task = create_market_research_task(market_agent)
    financial_analysis_task = create_financial_advisor_task(financial_agent, market_research_task)
    product_strategy_task = create_product_strategy_task(product_agent, financial_analysis_task)
    summary_task = create_summary_task(summary_agent, [market_research_task, financial_analysis_task, product_strategy_task])

    return Crew(
        agents=[
            create_market_research_agent(),
            create_product_strategist_agent(),
            create_financial_advisor_agent(),
            create_summary_agent()
        ],
        tasks=[
            market_research_task,
            financial_analysis_task,
            product_strategy_task,
            summary_task
        ]
    )