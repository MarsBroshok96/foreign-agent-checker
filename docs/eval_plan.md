# Evaluation Plan — Foreign Agent Article Checker

## Цель eval set

Eval set нужен для проверки качества и регрессионной устойчивости решения.

Машиночитаемый eval set находится в:

```text
tests/eval_cases/basic_eval.json
```

Лёгкий runner находится в:

```text
scripts/run_eval.py
```

Основные команды:

```bash
make eval-deterministic
make eval-no-llm
make eval-agentic
make eval-all
```

`eval-deterministic` и `eval-no-llm` не требуют Ollama. Agentic eval запускает
локальный bounded LLM review и требует работающий Ollama.

Он должен подтвердить, что система корректно обрабатывает:

1. Strong exact matches.
2. Weak alias matches.
3. Common-word false positives.
4. Person-only fuzzy matching.
5. Author check.
6. Resource link check.
7. Agentic disambiguation of weak candidates.

Eval set не является юридической проверкой и не делает выводов о нарушении закона. Он проверяет техническое поведение пайплайна.

---

## Архитектура, которую проверяем

Система состоит из двух основных режимов.

### Deterministic mode

Выполняет:

- article loading / extraction;
- registry loading;
- exact / alias matching;
- optional person-only fuzzy matching;
- label checking;
- author check;
- full resource link check;
- deterministic risk scoring;
- report rendering.

LLM не вызывается.

### Agentic mode

Выполняет deterministic baseline, затем:

- берёт только weak (/fuzzy) candidates;
- применяет bounded LLM review;
- использует локальные context profiles;
- не ходит в интернет;
- не меняет source of truth;
- возвращает результат в deterministic scorer.

---

## Общие правила оценки

### Strict pass

Используется для deterministic cases.

Ожидаемый результат должен совпасть строго:

- status;
- finding count;
- author check;
- resource link matches;
- fuzzy candidate count;
- human review flag.

### Acceptable pass

Используется для agentic cases, где LLM может вести себя не полностью стабильно.

Например:

- expected: rejected;
- acceptable: uncertain + requires_human_review=true;
- bad: confirmed without human review.

### Dangerous failure

Dangerous failure — это результат, который ухудшает compliance posture.

Примеры:

- false positive стал confirmed без human review;
- common word usage подтверждён как registry entity;
- fuzzy candidate стал confirmed без disambiguation;
- resource link matched only by domain, not full URL;
- author weak match стал strong без оснований.

---

## Ключевые метрики

Для каждого eval run желательно фиксировать:

- total cases;
- strict passed;
- acceptable passed;
- failed;
- dangerous failures;
- deterministic failures;
- agentic failures.

---

## Eval cases

| ID | Layer | Mode | Fuzzy | Purpose | Input | Registry setup | Expected | Acceptable | Bad |
|---|---|---|---|---|---|---|---|---|---|

### Case 01 — strong_person_name_match

| Field | Value |
|---|---|
| Layer | deterministic |
| Mode | deterministic |
| Fuzzy | false |
| Purpose | Проверить strong name-surname alias. |
| Article text | Илья Варламов прокомментировал ситуацию. |
| Author | Обычный Автор |
| Links | [] |
| Registry | Варламов Илья Александрович, entity_type=person |
| Expected | status=confirmed_match_found; finding.status=confirmed; match_type=exact; requires_human_review=false |
| Acceptable | none |
| Bad | no_match; uncertain; requires_human_review=true |

---

### Case 02 — weak_surname_only_match

| Field | Value |
|---|---|
| Layer | deterministic |
| Mode | deterministic |
| Fuzzy | false |
| Purpose | Проверить surname-only weak alias. |
| Article text | Варламов прокомментировал ситуацию. |
| Author | Обычный Автор |
| Links | [] |
| Registry | Варламов Илья Александрович, entity_type=person |
| Expected | status=potential_match_found; finding.status=uncertain; match_type=alias; requires_human_review=true |
| Acceptable | none |
| Bad | confirmed without human review; no_match |

---

### Case 03 — false_positive_white_house

| Field | Value |
|---|---|
| Layer | agentic |
| Mode | agentic |
| Fuzzy | false |
| Purpose | Проверить отклонение common phrase / institution false positive. |
| Article text | Белый дом выступил с заявлением после встречи. |
| Author | Обычный Автор |
| Links | [] |
| Registry | Белый Руслан Викторович, entity_type=person |
| Context profile | descriptors: комик, артист, телеведущий; common_mentions: Руслан Белый, Белый |
| Expected | status=no_match; finding.status=rejected; requires_human_review=false |
| Acceptable | status=potential_match_found; finding.status=uncertain; requires_human_review=true |
| Bad | confirmed/probable without human review |

---

### Case 04 — false_positive_after_rain

| Field | Value |
|---|---|
| Layer | agentic |
| Mode | agentic |
| Fuzzy | false |
| Purpose | Проверить common word usage для проекта «После». |
| Article text | После дождя движение на дорогах осложнилось. |
| Author | Обычный Автор |
| Links | [] |
| Registry | Проект «После», entity_type=project, aliases=[После] |
| Context profile | descriptors: медиа-проект; known_domains: posle.media; common_mentions: После |
| Expected | status=no_match; finding.status=rejected; requires_human_review=false |
| Acceptable | status=potential_match_found; finding.status=uncertain; requires_human_review=true |
| Bad | confirmed/probable without human review |

---

### Case 05 — true_positive_after_media_project

| Field | Value |
|---|---|
| Layer | agentic |
| Mode | agentic |
| Fuzzy | false |
| Purpose | Проверить, что проект «После» не всегда отклоняется как common word. |
| Article text | Издание После опубликовало новый материал. |
| Author | Обычный Автор |
| Links | [] |
| Registry | Проект «После», entity_type=project, aliases=[После] |
| Context profile | descriptors: медиа-проект; known_domains: posle.media; common_mentions: После |
| Expected | status=confirmed_match_found or potential_match_found; finding.status=same/probable equivalent; not rejected |
| Acceptable | finding.status=uncertain; requires_human_review=true |
| Bad | rejected |

---

### Case 06 — fuzzy_person_surname_case

| Field | Value |
|---|---|
| Layer | deterministic |
| Mode | deterministic |
| Fuzzy | true |
| Purpose | Проверить person-only fuzzy на родительный падеж фамилии. |
| Article text | Слова Варламова вызвали дискуссию. |
| Author | Обычный Автор |
| Links | [] |
| Registry | Варламов Илья Александрович, entity_type=person |
| Expected | status=potential_match_found; match_type=fuzzy; finding.status=uncertain; requires_human_review=true; deterministic_fuzzy_candidates=1 |
| Acceptable | none |
| Bad | no_match; confirmed without review |

---

### Case 07 — fuzzy_person_instrumental_case

| Field | Value |
|---|---|
| Layer | deterministic |
| Mode | deterministic |
| Fuzzy | true |
| Purpose | Проверить person-only fuzzy на творительный падеж фамилии. |
| Article text | С Венедиктовым обсудили ситуацию на рынке медиа. |
| Author | Обычный Автор |
| Links | [] |
| Registry | Венедиктов Алексей Алексеевич, entity_type=person |
| Expected | status=potential_match_found; match_type=fuzzy; finding.status=uncertain; requires_human_review=true |
| Acceptable | none |
| Bad | no_match; confirmed without review |

---

### Case 08 — fuzzy_person_multi_token_case

| Field | Value |
|---|---|
| Layer | deterministic |
| Mode | deterministic |
| Fuzzy | true |
| Purpose | Проверить fuzzy для двухсловного упоминания в падеже. |
| Article text | Илью Варламова спросили о проекте благоустройства. |
| Author | Обычный Автор |
| Links | [] |
| Registry | Варламов Илья Александрович, entity_type=person |
| Expected | status=potential_match_found; at least one fuzzy finding; requires_human_review=true |
| Acceptable | none |
| Bad | no_match; confirmed without review |

---

### Case 09 — fuzzy_safety_project_excluded

| Field | Value |
|---|---|
| Layer | deterministic |
| Mode | deterministic |
| Fuzzy | true |
| Purpose | Проверить, что fuzzy не применяется к project/media/org. |
| Article text | После дождя случилось событие. |
| Author | Обычный Автор |
| Links | [] |
| Registry | Проект «После», entity_type=project, aliases=[После] |
| Expected | deterministic_fuzzy_candidates=0; no fuzzy findings |
| Acceptable | exact weak alias may appear as alias, but not fuzzy |
| Bad | fuzzy match for project |

---

### Case 10 — fuzzy_safety_short_person_alias

| Field | Value |
|---|---|
| Layer | deterministic |
| Mode | deterministic |
| Fuzzy | true |
| Purpose | Проверить, что короткий one-token person alias не создаёт fuzzy noise. |
| Article text | Белый дом сделал заявление. |
| Author | Обычный Автор |
| Links | [] |
| Registry | Белый Руслан Викторович, entity_type=person |
| Expected | deterministic_fuzzy_candidates=0; no fuzzy findings |
| Acceptable | exact weak alias may appear as alias, but not fuzzy |
| Bad | fuzzy match for белый |

---

### Case 11 — author_strong_match

| Field | Value |
|---|---|
| Layer | deterministic |
| Mode | deterministic |
| Fuzzy | false |
| Purpose | Проверить strong author check. |
| Article text | Текст статьи без упоминаний. |
| Author | Илья Варламов |
| Links | [] |
| Registry | Варламов Илья Александрович, entity_type=person |
| Expected | status=confirmed_match_found; author_check.status=strong_match; author_check.requires_human_review=false |
| Acceptable | none |
| Bad | no_match; weak_match |

---

### Case 12 — author_weak_match

| Field | Value |
|---|---|
| Layer | deterministic |
| Mode | deterministic |
| Fuzzy | false |
| Purpose | Проверить weak author check. |
| Article text | Текст статьи без упоминаний. |
| Author | Варламов |
| Links | [] |
| Registry | Варламов Илья Александрович, entity_type=person |
| Expected | status=potential_match_found; author_check.status=weak_match; author_check.requires_human_review=true |
| Acceptable | none |
| Bad | confirmed_match_found without strong author match |

---

### Case 13 — author_no_match

| Field | Value |
|---|---|
| Layer | deterministic |
| Mode | deterministic |
| Fuzzy | false |
| Purpose | Проверить no-match author check. |
| Article text | Текст статьи без упоминаний. |
| Author | Андрей Дуванов |
| Links | [] |
| Registry | Варламов Илья Александрович, entity_type=person |
| Expected | status=no_match; author_check.status=no_match |
| Acceptable | none |
| Bad | potential_match_found; confirmed_match_found |

---

### Case 14 — resource_link_full_match

| Field | Value |
|---|---|
| Layer | deterministic |
| Mode | deterministic |
| Fuzzy | false |
| Purpose | Проверить full URL resource link match. |
| Article text | Текст статьи без упоминаний. |
| Author | Обычный Автор |
| Links | https://posle.media/ |
| Registry | Проект «После», entity_type=project, raw_fields.resource_urls=[https://posle.media/] |
| Expected | status=confirmed_match_found; resource_link_matches=1; entity=Проект «После» |
| Acceptable | none |
| Bad | no_match |

---

### Case 15 — resource_link_domain_only_no_match

| Field | Value |
|---|---|
| Layer | deterministic |
| Mode | deterministic |
| Fuzzy | false |
| Purpose | Проверить, что domain-only совпадение не засчитывается. |
| Article text | Текст статьи без упоминаний. |
| Author | Обычный Автор |
| Links | https://t.me/other |
| Registry | Проект «После», entity_type=project, raw_fields.resource_urls=[https://t.me/poslemedia] |
| Expected | status=no_match; resource_link_matches=0 |
| Acceptable | none |
| Bad | confirmed_match_found due domain-only match |

---

### Case 16 — label_present_near_exact_match

| Field | Value |
|---|---|
| Layer | deterministic |
| Mode | deterministic |
| Fuzzy | false |
| Purpose | Проверить label checker при nearby label. |
| Article text | Илья Варламов, признан иностранным агентом, прокомментировал ситуацию. |
| Author | Обычный Автор |
| Links | [] |
| Registry | Варламов Илья Александрович, entity_type=person |
| Expected | status=confirmed_match_found; finding.status=confirmed; label_status=present; risk_level=low; requires_human_review=false |
| Acceptable | none |
| Bad | label_status=absent |

---

### Case 17 — label_absent_exact_match

| Field | Value |
|---|---|
| Layer | deterministic |
| Mode | deterministic |
| Fuzzy | false |
| Purpose | Проверить risk при exact match без маркировки. |
| Article text | Илья Варламов прокомментировал ситуацию. |
| Author | Обычный Автор |
| Links | [] |
| Registry | Варламов Илья Александрович, entity_type=person |
| Expected | status=confirmed_match_found; finding.status=confirmed; label_status=absent; risk_level=high; requires_human_review=true |
| Acceptable | none |
| Bad | risk_level=low; requires_human_review=false |

---

### Case 18 — mixed_strong_and_rejected_weak

| Field | Value |
|---|---|
| Layer | agentic |
| Mode | agentic |
| Fuzzy | false |
| Purpose | Проверить смешанный кейс: strong true positive + weak false positive. |
| Article text | Илья Варламов прокомментировал ситуацию. Позже Белый дом выступил с заявлением. |
| Author | Обычный Автор |
| Links | [] |
| Registry | Варламов Илья Александрович; Белый Руслан Викторович |
| Context profiles | profiles for Варламов and Белый |
| Expected | status=confirmed_match_found; Варламов confirmed; Белый rejected or uncertain+human_review |
| Acceptable | Белый uncertain+human_review |
| Bad | Варламов missing; Белый confirmed without human review |

---

## Notes for future automation

The first version of this eval set may be manual.

Later it can be converted into:

- tests/eval_cases/basic_eval.json
- scripts/run_eval.py
- make eval-deterministic
- make eval-agentic

Recommended eval runner behavior:

- deterministic cases should be strict;
- agentic cases may support acceptable outcomes;
- dangerous failures should be highlighted separately.

Recommended output:

- PASS
- ACCEPTABLE
- FAIL
- DANGEROUS_FAIL

Recommended summary:

- total cases
- passed
- acceptable
- failed
- dangerous failures
