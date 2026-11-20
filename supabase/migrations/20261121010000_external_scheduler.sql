-- External scheduler: GitHub's own cron has never fired, so Supabase pg_cron asks GitHub to start the workflows.
-- The GitHub token (fine-grained, Actions: write on this repo only) lives in Supabase Vault under the name
-- 'github_dispatch_token'; scripts/setup-scheduler.sh stores it. Without the token the jobs do nothing.
create extension if not exists pg_net;
create extension if not exists pg_cron;

create or replace function public.dispatch_workflow(workflow text)
returns bigint language plpgsql security definer set search_path = '' as $$
declare tok text;
begin
  select decrypted_secret into tok from vault.decrypted_secrets where name = 'github_dispatch_token' limit 1;
  if tok is null then return null; end if;
  return net.http_post(
    url := 'https://api.github.com/repos/Shubh-desai7/live-show-radar/actions/workflows/' || workflow || '/dispatches',
    headers := jsonb_build_object('Authorization', 'Bearer ' || tok, 'Accept', 'application/vnd.github+json',
                                  'X-GitHub-Api-Version', '2022-11-28', 'User-Agent', 'live-show-radar-scheduler',
                                  'Content-Type', 'application/json'),
    body := '{"ref":"main"}'::jsonb);
end $$;
revoke all on function public.dispatch_workflow(text) from public, anon, authenticated;

select cron.schedule('dispatch-discover', '7,37 * * * *', $$select public.dispatch_workflow('discover.yml')$$);
select cron.schedule('dispatch-remind', '*/15 * * * *', $$select public.dispatch_workflow('remind.yml')$$);
