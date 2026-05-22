import { createClient } from "@supabase/supabase-js";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string;

if (!supabaseUrl || !supabaseAnonKey) {
  console.warn(
    "[ConX] VITE_SUPABASE_URL/VITE_SUPABASE_ANON_KEY non définis. " +
      "Auth désactivée en dev — mode anonyme.",
  );
}

export const supabase = createClient(
  supabaseUrl ?? "http://localhost:54321",
  supabaseAnonKey ?? "anon-dev-noop",
  {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
    },
  },
);

/** Renvoie le JWT courant ou null si non logué. */
export async function getCurrentJwt(): Promise<string | null> {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}
