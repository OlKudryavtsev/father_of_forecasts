-- v3.3.1 — hotfix for Stage 3/4 question types.
-- v3.2.0 added true_false, more_less and yes_no in application code, but
-- migration 025 did not extend the original PostgreSQL CHECK constraint.
-- Apply after migrations 023–026 and before loading the WC-2026 Stage 4 test bank.

BEGIN;

ALTER TABLE league_quiz_questions
    DROP CONSTRAINT IF EXISTS chk_league_quiz_question_type;

ALTER TABLE league_quiz_questions
    ADD CONSTRAINT chk_league_quiz_question_type CHECK (question_type IN (
        'choice_2',
        'choice_4',
        'true_false',
        'more_less',
        'yes_no',
        'jeopardy',
        'one_of_two',
        'what_where_when',
        'countdown',
        'hundred_to_one'
    ));

COMMIT;
