-- Run once in your Supabase project's SQL Editor (or via supabase db push).
-- Supabase Auth owns accounts/emails/passwordless sessions; this table stores preferences only.
begin;
create table if not exists public.bol_preferences (
  user_id uuid primary key references auth.users(id) on delete cascade,
  payload jsonb not null default '{}'::jsonb,
  revision bigint not null default 0 check (revision >= 0),
  updated_at timestamptz not null default now(),
  constraint bol_payload_object check (jsonb_typeof(payload) = 'object'),
  constraint bol_payload_size check (octet_length(payload::text) <= 65536),
  constraint bol_payload_fields check (payload - array['profile_name','theme','start_page','language','output_mode','polish','writing_rules','profiles','vocabulary','corrections','snippets','review_edits']::text[] = '{}'::jsonb)
);
alter table public.bol_preferences enable row level security;
revoke all on public.bol_preferences from anon, authenticated;
grant select, insert, update on public.bol_preferences to authenticated;
drop policy if exists bol_owner_select on public.bol_preferences;
create policy bol_owner_select on public.bol_preferences for select to authenticated using ((select auth.uid()) = user_id);
drop policy if exists bol_owner_insert on public.bol_preferences;
create policy bol_owner_insert on public.bol_preferences for insert to authenticated with check ((select auth.uid()) = user_id);
drop policy if exists bol_owner_update on public.bol_preferences;
create policy bol_owner_update on public.bol_preferences for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

-- Compare-and-swap prevents one device silently overwriting another device's edits.
create or replace function public.bol_save_preferences(new_payload jsonb, expected_revision bigint)
returns bigint language plpgsql security invoker set search_path = '' as $$
declare next_revision bigint;
begin
  if auth.uid() is null then raise insufficient_privilege; end if;
  insert into public.bol_preferences(user_id) values(auth.uid()) on conflict do nothing;
  update public.bol_preferences
    set payload = new_payload, revision = revision + 1, updated_at = now()
    where user_id = auth.uid() and revision = expected_revision
    returning revision into next_revision;
  if next_revision is null then
    raise sqlstate 'PT409' using message = 'Cloud preferences changed on another device';
  end if;
  return next_revision;
end;
$$;
revoke all on function public.bol_save_preferences(jsonb, bigint) from public, anon;
grant execute on function public.bol_save_preferences(jsonb, bigint) to authenticated;
commit;
