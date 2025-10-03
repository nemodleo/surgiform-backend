import os
import time
import json
from datetime import datetime
from openai import OpenAI
import statistics
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Test models (only using real OpenAI models)
MODELS = [
    'gpt-5',
    'gpt-5-mini',
    'gpt-5-nano',
    'gpt-4.1',
    'gpt-4.1-mini',
    'gpt-4.1-nano',
    'gpt-4o',
    'gpt-4o-mini',
    'o4-mini',
    'o3-mini',
    'o1-mini',
    'gpt-3.5-turbo',
]

# Test tasks
TASKS = {
    '100자_한영번역': {
        'prompt': '다음 100자 한글 텍스트를 영어로 번역해주세요: "인공지능 기술의 발전은 우리 삶의 많은 부분을 변화시키고 있습니다. 특히 자연어 처리 기술은 언어의 장벽을 넘어 전 세계 사람들이 소통할 수 있도록 돕고 있으며, 이는 글로벌 협력과 이해를 증진시키는 데 크게 기여하고 있습니다."',
        'description': '100자 한영번역'
    },
    '대동맥_수술_설명': {
        'prompt': '대동맥 파열/박리 수술에 대해 설명해주세요.',
        'description': '대동맥 파열/박리 수술 설명'
    },
    '100자_20자_요약': {
        'prompt': '다음 텍스트를 20자 이내로 요약해주세요: "인공지능 기술의 발전은 우리 삶의 많은 부분을 변화시키고 있습니다. 특히 자연어 처리 기술은 언어의 장벽을 넘어 전 세계 사람들이 소통할 수 있도록 돕고 있습니다."',
        'description': '100자를 20자로 요약'
    }
}

def measure_speed(model, task_name, task):
    """Measure response speed for a given model and task"""
    try:
        start_time = time.time()

        # Special handling for o-series models (reasoning models)
        if model.startswith('o'):
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": task['prompt']}
                ]
            )
        # GPT-5 series uses max_completion_tokens and only supports temperature=1
        elif model.startswith('gpt-5'):
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": task['prompt']}
                ],
                max_completion_tokens=500
            )
        else:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": task['prompt']}
                ],
                temperature=0.7,
                max_tokens=500
            )

        end_time = time.time()
        elapsed_time = end_time - start_time

        return {
            'success': True,
            'time': elapsed_time,
            'response': response.choices[0].message.content,
            'tokens': response.usage.total_tokens if hasattr(response, 'usage') else 0
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'time': 0,
            'response': '',
            'tokens': 0
        }

def run_benchmark(iterations=3):
    """Run benchmark for all models and tasks"""
    results = {}

    print("🚀 Starting OpenAI Model Benchmark...")
    print(f"📅 Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔄 Iterations per test: {iterations}\n")

    for model in MODELS:
        print(f"\n📊 Testing model: {model}")
        results[model] = {}

        for task_name, task in TASKS.items():
            print(f"  ⏳ Running task: {task['description']}...", end=' ')
            times = []
            tokens = []
            responses = []

            for i in range(iterations):
                result = measure_speed(model, task_name, task)
                if result['success']:
                    times.append(result['time'])
                    tokens.append(result['tokens'])
                    responses.append(result['response'])
                else:
                    print(f"\n  ❌ Error: {result['error']}")
                    break

            if times:
                avg_time = statistics.mean(times)
                results[model][task_name] = {
                    'avg_time': avg_time,
                    'min_time': min(times),
                    'max_time': max(times),
                    'avg_tokens': statistics.mean(tokens) if tokens else 0,
                    'all_times': times,
                    'sample_response': responses[0] if responses else ''
                }
                print(f"✅ Avg: {avg_time:.2f}s")
            else:
                results[model][task_name] = {
                    'avg_time': 0,
                    'min_time': 0,
                    'max_time': 0,
                    'avg_tokens': 0,
                    'all_times': [],
                    'sample_response': '',
                    'error': result.get('error', 'Unknown error')
                }

    return results

def generate_report(results):
    """Generate markdown report"""
    report = []
    report.append("# OpenAI Model Performance Benchmark Report\n")
    report.append(f"**Test Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    report.append(f"**Number of iterations**: 3\n\n")

    report.append("## Executive Summary\n")
    report.append("This report compares the performance of various OpenAI models across three tasks:\n")
    report.append("- 100자 한영번역 (Korean to English translation)\n")
    report.append("- 100자 생성 (Text generation)\n")
    report.append("- 100자 10자로 요약 (Text summarization)\n\n")

    # Performance comparison table
    report.append("## Performance Comparison Table\n\n")

    for task_name, task_info in TASKS.items():
        report.append(f"### {task_info['description']}\n\n")
        report.append("| Model | Avg Time (s) | Min Time (s) | Max Time (s) | Avg Tokens |\n")
        report.append("|-------|--------------|--------------|--------------|------------|\n")

        # Sort by average time
        sorted_models = sorted(
            [(model, data.get(task_name, {})) for model, data in results.items()],
            key=lambda x: x[1].get('avg_time', float('inf'))
        )

        for model, data in sorted_models:
            if data and 'error' not in data:
                report.append(
                    f"| {model} | {data['avg_time']:.3f} | {data['min_time']:.3f} | "
                    f"{data['max_time']:.3f} | {data['avg_tokens']:.0f} |\n"
                )
            else:
                error_msg = data.get('error', 'N/A') if data else 'N/A'
                report.append(f"| {model} | ❌ Error | - | - | - |\n")

        report.append("\n")

    # Sample responses
    report.append("## Sample Responses\n\n")
    for task_name, task_info in TASKS.items():
        report.append(f"### {task_info['description']}\n\n")
        report.append(f"**Prompt**: {task_info['prompt']}\n\n")

        for model in MODELS:
            if model in results and task_name in results[model]:
                sample = results[model][task_name].get('sample_response', '')
                if sample:
                    report.append(f"**{model}**:\n```\n{sample}\n```\n\n")

    # Fastest model summary
    report.append("## Fastest Models by Task\n\n")
    for task_name, task_info in TASKS.items():
        fastest = min(
            [(model, data.get(task_name, {}).get('avg_time', float('inf')))
             for model, data in results.items()],
            key=lambda x: x[1]
        )
        if fastest[1] != float('inf'):
            report.append(f"- **{task_info['description']}**: {fastest[0]} ({fastest[1]:.3f}s)\n")

    return ''.join(report)

if __name__ == "__main__":
    # Check API key
    if not os.getenv('OPENAI_API_KEY'):
        print("❌ Error: OPENAI_API_KEY environment variable not set")
        exit(1)

    # Run benchmark
    results = run_benchmark(iterations=3)

    # Save results as JSON
    with open('benchmark_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("\n\n💾 Results saved to benchmark_results.json")

    # Generate and save report
    report = generate_report(results)
    with open('benchmark_report.md', 'w', encoding='utf-8') as f:
        f.write(report)
    print("📄 Report saved to benchmark_report.md")

    print("\n✅ Benchmark complete!")
