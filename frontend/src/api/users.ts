//users.ts 
export interface UseRow {
    id: number;
    email: string;
    role?: string | null;
    is_active: boolean;
}