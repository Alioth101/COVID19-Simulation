import json
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from covid_abs.experiments import batch_experiment
from covid_abs.network.graph_abs import GraphSimulation


def load_config(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def run_config(config_path, experiments=35, iterations=1440, output_dir=None, backend=None, enable_llm=True):
    config = load_config(config_path)
    cfg_name = config.get('name', os.path.basename(config_path))

    # Prepare output path
    if output_dir is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(script_dir, '..', 'output', 'paper_benchmark')
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_file = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(config_path))[0]}_{timestamp}.csv")
    llm_log_file = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(config_path))[0]}_{timestamp}_llm.json") if enable_llm else None

    # Merge config into kwargs for batch_experiment
    kwargs = dict(config)
    # Ensure compatible names with batch_experiment / GraphSimulation
    kwargs['population_size'] = config.get('population_size', config.get('total_population', 300))
    kwargs['length'] = config.get('length', 200)
    kwargs['height'] = config.get('height', 200)
    kwargs['initial_infected_perc'] = config.get('initial_infected_perc', 0.01)
    kwargs['initial_immune_perc'] = config.get('initial_immune_perc', 0.01)
    kwargs['contagion_distance'] = config.get('contagion_distance', 1.0)
    kwargs['contagion_rate'] = config.get('contagion_rate', 0.9)
    kwargs['incubation_time'] = config.get('incubation_time', 5)
    kwargs['contagion_time'] = config.get('contagion_time', 10)
    kwargs['recovering_time'] = config.get('recovering_time', 20)
    kwargs['critical_limit'] = config.get('critical_limit', 0.05)
    kwargs['total_business'] = config.get('total_business', 10)
    kwargs['homemates_avg'] = config.get('homemates_avg', 3)
    kwargs['homeless_rate'] = config.get('homeless_rate', 0.01)
    kwargs['unemployment_rate'] = config.get('unemployment_rate', 0.09)

    # LLM specific
    kwargs['enable_llm_decision'] = config.get('enable_llm_decision', enable_llm)
    if enable_llm:
        kwargs['backend'] = backend
        kwargs['max_concurrent_llm'] = config.get('max_concurrent_llm', 3)
        kwargs['decision_interval'] = config.get('decision_interval', 6)

    # Add triggers if present (careful: JSON contains strings for lambdas)
    if 'triggers_simulation' in config:
        # User must edit file manually to inject actual lambda objects if needed
        print('Note: triggers_simulation present in config but require manual conversion from string to lambda.')
        del kwargs['triggers_simulation']

    print(f"Running benchmark: {cfg_name}\n  experiments={experiments}, iterations={iterations}")

    df = batch_experiment(
        experiments=experiments,
        iterations=iterations,
        file=csv_file,
        simulation_type=GraphSimulation,
        llm_log_file=llm_log_file,
        verbose='experiments',
        **kwargs
    )

    print(f"Results saved to: {csv_file}")
    if llm_log_file:
        print(f"LLM logs saved to: {llm_log_file}")

    return df


if __name__ == '__main__':
    import argparse
    from covid_abs.llm.openai_backend import OpenAIBackend

    parser = argparse.ArgumentParser()
    parser.add_argument('config', help='Path to scenario JSON in configs folder')
    parser.add_argument('--experiments', type=int, default=35)
    parser.add_argument('--iterations', type=int, default=1440)
    parser.add_argument('--no-llm', dest='enable_llm', action='store_false')
    args = parser.parse_args()

    # Create backend if enabling LLM
    backend = None
    if args.enable_llm:
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            print('No OPENAI_API_KEY found in environment. Set it or run with --no-llm')
            sys.exit(1)
        backend = OpenAIBackend(model_name='gpt-4o-mini', temperature=0.7, max_tokens=500)

    run_config(os.path.abspath(args.config), experiments=args.experiments, iterations=args.iterations, backend=backend, enable_llm=args.enable_llm)
