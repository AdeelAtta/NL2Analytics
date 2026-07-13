import { useAuthStore } from "@/stores/auth";

export interface SessionUser {
  id: string;
  name: string;
  email: string;
  role: "admin" | "analyst" | "viewer";
  avatar?: string;
}

export interface Session {
  user: SessionUser;
  expires: string;
}

export function useSession(): { data: Session | null; status: "loading" | "authenticated" | "unauthenticated" } {
  const { isAuthenticated, userId, email, name, role } = useAuthStore();
  if (!isAuthenticated) return { data: null, status: "unauthenticated" };
  return {
    data: {
      user: { id: userId, name, email, role: role as Session["user"]["role"] },
      expires: "",
    },
    status: "authenticated",
  };
}

export function signIn(): void {
  useAuthStore.getState().login();
}

export function signOut(): void {
  useAuthStore.getState().logout();
}
