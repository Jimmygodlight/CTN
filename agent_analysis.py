import json
from pathlib import Path
from difflib import SequenceMatcher

folder = Path(__file__).resolve().parent / "data"


def similarity(text1, text2):
    return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()


def find_similar_accounts(posts):
    results = {}
    for i in range(len(posts)):
        for j in range(i + 1, len(posts)):
            post1 = posts[i]
            post2 = posts[j]
            if not isinstance(post1, dict) or not isinstance(post2, dict):
                continue
            user1 = str(post1.get("author_id") or "")
            user2 = str(post2.get("author_id") or "")
            if not user1 or not user2 or user1 == user2:
                continue
            text1 = str(post1.get("body") or "").strip()
            text2 = str(post2.get("body") or "").strip()
            if len(text1) < 20 or len(text2) < 20:
                continue
            if similarity(text1, text2) >= 0.8:
                pair = tuple(sorted([user1, user2]))
                results[pair] = results.get(pair, 0) + 1
    return results


def find_groups(pairs):
    groups = []
    for user1, user2 in pairs:
        matching = []
        for group in groups:
            if user1 in group or user2 in group:
                matching.append(group)
        new_group = {user1, user2}
        for group in matching:
            new_group.update(group)
            groups.remove(group)
        groups.append(new_group)
    return [sorted(group) for group in groups]


def main():
    file = folder / "trending.json"
    if not file.exists():
        print("No data/trending.json found. Run your existing main.py first.")
        return
    with open(file, encoding="utf-8") as f:
        data = json.load(f)
    posts = data if isinstance(data, list) else data.get("posts", [])
    if not isinstance(posts, list):
        print("Expected a list of posts in trending.json")
        return

    pairs = find_similar_accounts(posts)
    groups = find_groups(pairs)
    print("Analysed", len(posts), "posts")
    print("Similar account pairs:")
    for pair, count in pairs.items():
        print(pair, "matching post pairs:", count)
    print("Potential groups:")
    for group in groups:
        print(group)

    results = {
        "similar_pairs": [
            {"accounts": list(pair), "matching_post_pairs": count}
            for pair, count in pairs.items()
        ],
        "groups": groups,
        "note": "Similarity groups are not proof of bots, coordination, or NPC identity."
    }
    folder.mkdir(exist_ok=True)
    with open(folder / "agent_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("Saved data/agent_results.json")


if __name__ == "__main__":
    main()
