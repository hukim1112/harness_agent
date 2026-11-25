"""
===============================================================================
Skill Prompt Builder — Frontmatter Scanner & Dynamic Catalog Builder
===============================================================================
스킬 행동 수칙(가이드라인) + 설치된 스킬 디렉토리(SKILL.md / *.md)의 YAML Frontmatter를
스캔하여 구조화된 스킬 목록(list_skills)과 <skills> 카탈로그(build_catalog)를 생성합니다.
===============================================================================
"""

import os
import re
from typing import Dict, List, Optional, Tuple


class SkillPromptBuilder:
    """스킬 행동 수칙(가이드라인) + 설치된 스킬 카탈로그(프론트매터) 통합 조립기"""

    DEFAULT_GUIDELINES = """## Skill Execution Policy
1. 사용자의 요청을 해결할 수 있는 스킬이 카탈로그에 있다면, raw 셸 명령보다 해당 스킬을 우선 활용하세요.
2. 스킬을 사용하기 전, 반드시 `file_read`로 해당 스킬의 문서(`SKILL.md` 또는 `.md`)를 열람하여 정확한 파라미터와 실행법을 파악하세요.
3. 지침에 따라 `bash_command`로 스크립트를 실행하거나 가이드 절차를 수행해 작업을 완료하세요."""

    def __init__(
        self,
        skills_dirs: Optional[List[str]] = None,
        guidelines_path: Optional[str] = "app/prompts/SKILL.md",
    ):
        self.skills_dirs = skills_dirs or ["./skills", "./.agents/skills", "skills", "../skills"]
        self.guidelines_path = guidelines_path

    def _extract_frontmatter(self, skill_md_path: str) -> Dict[str, str]:
        """SKILL.md 상단의 YAML Frontmatter(name, description) 추출 (없으면 제목/설명 폴백)"""
        try:
            with open(skill_md_path, "r", encoding="utf-8") as f:
                content = f.read(2048)  # 상단 2KB 읽기 (I/O 최적화)

            # 1. --- ... --- 사이의 YAML Frontmatter 정규식 추출
            match = re.search(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
            if match:
                meta: Dict[str, str] = {}
                for line in match.group(1).strip().splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        meta[k.strip().lower()] = v.strip().strip("\"'")
                if meta.get("name") or meta.get("description"):
                    return meta

            # 2. Frontmatter가 없을 때의 마크다운 폴백 (# Title 및 첫 문단)
            meta = {}
            lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
            for line in lines:
                if line.startswith("# ") and "name" not in meta:
                    meta["name"] = line.replace("# ", "").replace("Skill", "").strip()
                elif not line.startswith("#") and not line.startswith("---") and "description" not in meta:
                    meta["description"] = line
            return meta
        except Exception:
            return {}

    def _scan_candidates(self) -> List[Tuple[str, str]]:
        """스킬 디렉토리에서 (기본 이름, 문서 경로) 후보를 찾습니다 (폴더형 SKILL.md + 낱개 .md)."""
        candidates: List[Tuple[str, str]] = []
        for base_dir in self.skills_dirs:
            if not os.path.exists(base_dir):
                continue

            try:
                entries = sorted(os.listdir(base_dir))
            except Exception:
                continue

            # 1. 낱개 마크다운 스킬 파일 (예: app/agents/analyst/skills/chart_patterns.md)
            for item_name in entries:
                item_path = os.path.join(base_dir, item_name)
                if (
                    os.path.isfile(item_path)
                    and item_name.lower().endswith(".md")
                    and item_name not in ("SKILL.md", "Skill.md", "skill.md", "README.md")
                ):
                    stem = os.path.splitext(item_name)[0]
                    candidates.append((stem, item_path))

            # 2. 폴더형 스킬 (예: skills/pykrx-korean-market/SKILL.md)
            for folder_name in entries:
                dir_path = os.path.join(base_dir, folder_name)
                if not os.path.isdir(dir_path):
                    continue
                for fname in ("SKILL.md", "Skill.md", "skill.md"):
                    candidate = os.path.join(dir_path, fname)
                    if os.path.exists(candidate):
                        candidates.append((folder_name, candidate))
                        break

        return candidates

    def _scan_signature(self) -> Tuple:
        """스킬 디렉토리 변경 감지를 위한 경량 서명: (경로, mtime_ns, size) 정렬 튜플."""
        sig = []
        for base_dir in self.skills_dirs:
            try:
                st_dir = os.stat(base_dir)
                sig.append((base_dir, st_dir.st_mtime_ns, st_dir.st_size))
                with os.scandir(base_dir) as it:
                    for entry in it:
                        if entry.is_dir():
                            for fname in ("SKILL.md", "Skill.md", "skill.md"):
                                p = os.path.join(entry.path, fname)
                                if os.path.exists(p):
                                    st_f = os.stat(p)
                                    sig.append((p, st_f.st_mtime_ns, st_f.st_size))
                                    break
                        elif entry.name.lower().endswith(".md"):
                            st_f = entry.stat()
                            sig.append((entry.path, st_f.st_mtime_ns, st_f.st_size))
            except OSError:
                sig.append((base_dir, None, None))
        return tuple(sorted(sig, key=lambda x: x[0]))

    def list_skills(self) -> List[Dict[str, str]]:
        """설치된 스킬을 [{"name", "description", "path"}] 목록으로 반환합니다 (이름순)."""
        signature = self._scan_signature()
        cached = getattr(self, "_list_cache", None)
        if cached and cached[0] == signature:
            return list(cached[1])

        skills: List[Dict[str, str]] = []
        seen_paths = set()
        seen_names = set()
        guidelines_abs = (
            os.path.normcase(os.path.abspath(self.guidelines_path))
            if self.guidelines_path and os.path.exists(self.guidelines_path)
            else None
        )

        for default_name, skill_file in self._scan_candidates():
            abs_key = os.path.normcase(os.path.abspath(skill_file))
            if abs_key == guidelines_abs or abs_key in seen_paths:
                continue

            meta = self._extract_frontmatter(skill_file)
            if not meta:
                continue

            name = meta.get("name", default_name)
            if name in seen_names:
                continue

            seen_paths.add(abs_key)
            seen_names.add(name)
            try:
                rel_path = os.path.relpath(skill_file).replace("\\", "/")
            except ValueError:
                rel_path = os.path.abspath(skill_file).replace("\\", "/")

            skills.append({
                "name": name,
                "description": " ".join(meta.get("description", "No description provided.").split()),
                "path": rel_path,
            })

        skills.sort(key=lambda s: s["name"])
        self._list_cache = (signature, skills)
        return list(skills)

    def load_guidelines(self) -> str:
        """스킬 실행 지침(guidelines_path 파일, 없으면 기본 지침)을 반환합니다."""
        if self.guidelines_path and os.path.exists(self.guidelines_path):
            try:
                with open(self.guidelines_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if content:
                    return content
            except Exception:
                pass
        return self.DEFAULT_GUIDELINES

    def build_catalog(self, skills: Optional[List[Dict[str, str]]] = None) -> str:
        """스킬 목록을 <skills> 카탈로그 텍스트로 렌더링합니다."""
        items = skills if skills is not None else self.list_skills()
        catalog_entries = [
            f"- **{s['name']}** (`{s['path']}`):\n    {s['description']}" for s in items
        ]
        if not catalog_entries:
            return "No custom skills currently registered in local `skills/` directory."
        return "<skills>\n" + "\n".join(catalog_entries) + "\n</skills>"

    def assemble(self) -> str:
        """가이드라인 + 카탈로그를 하나로 조립하여 반환합니다."""
        guidelines = self.load_guidelines()
        catalog = self.build_catalog()
        return f"{guidelines}\n\n### Available Skills Catalog\n{catalog}"
