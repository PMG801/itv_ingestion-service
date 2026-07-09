"""Debug script to inspect LLM batch response."""
import asyncio
import json
from domain.itv_stations.transformers.llm_transformer import LLMTransformer
from pathlib import Path

async def test_batch():
    # Load fixtures
    fixtures_dir = Path("tests/fixtures")
    
    # Load 3 Catalunya records
    xml_payload = (fixtures_dir / "catalunya_sample.xml").read_text(encoding="utf-8")
    batch = [xml_payload] * 3
    
    # Transform
    transformer = LLMTransformer(source_system="catalunya")
    results = await transformer.transform_batch_async(batch)
    
    print(f"Input batch size: {len(batch)}")
    print(f"Output results size: {len(results)}")
    print(f"LLM last_metrics: {transformer.last_metrics}")
    print(f"LLM last_generated_mapping size: {len(transformer.last_generated_mapping)}")
    
    if transformer.last_generated_mapping:
        print(f"\nFirst mapped item (LLM response):")
        print(json.dumps(transformer.last_generated_mapping[0], indent=2)[:500])

asyncio.run(test_batch())
