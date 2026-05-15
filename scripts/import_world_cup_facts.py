import json
from pathlib import Path

from app.db import SessionLocal
from app.models import WorldCupFact


SEED_PATH = Path("data/world_cup_facts_seed.json")


def main():
    if not SEED_PATH.exists():
        raise FileNotFoundError(f"Seed file not found: {SEED_PATH}")

    payload = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    facts = payload["facts"]

    db = SessionLocal()

    created = 0
    updated = 0

    try:
        for item in facts:
            external_id = item["id"]

            fact = db.query(WorldCupFact).filter(
                WorldCupFact.external_id == external_id
            ).first()

            if not fact:
                fact = WorldCupFact(external_id=external_id)
                db.add(fact)
                created += 1
            else:
                updated += 1

            fact.title = item["title"]
            fact.fact_text = item["fact_text"]
            fact.category = item.get("category")
            fact.tournament_year = item.get("tournament_year")
            fact.source_text = item.get("source_text")
            fact.source_url = item.get("source_url")
            fact.spicy_comment = item.get("spicy_comment")
            fact.needs_verification = bool(item.get("needs_verification", False))
            fact.is_active = bool(item.get("is_active", True))

        db.commit()

        print(f"Imported facts: {len(facts)}")
        print(f"Created: {created}")
        print(f"Updated: {updated}")

    finally:
        db.close()


if __name__ == "__main__":
    main()