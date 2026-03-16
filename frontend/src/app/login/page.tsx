'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';
import { login as apiLogin, getMe } from '@/lib/api';
import { useAuthStore } from '@/lib/auth-store';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const { setAuth, hydrate, token } = useAuthStore();

  useEffect(() => { hydrate(); }, [hydrate]);
  useEffect(() => { if (token) router.push('/dashboard'); }, [token, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const { access_token } = await apiLogin(email, password);
      localStorage.setItem('token', access_token);
      const user = await getMe();
      setAuth(access_token, user);
      router.push('/dashboard');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Login fehlgeschlagen');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <h1 className="text-xl font-bold">📗 RDS Buchhaltung</h1>
          <p className="text-sm text-gray-500">Anmelden</p>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <Input type="email" placeholder="E-Mail" value={email} onChange={(e) => setEmail(e.target.value)} required />
            <Input type="password" placeholder="Passwort" value={password} onChange={(e) => setPassword(e.target.value)} required />
            {error && <p className="text-sm text-red-500">{error}</p>}
            <Button type="submit" className="w-full" disabled={loading}>{loading ? 'Laden...' : 'Anmelden'}</Button>
          </form>
          <p className="text-center text-sm text-gray-500 mt-4">
            Noch kein Konto? <a href="/register" className="text-brand-600 hover:underline">Registrieren</a>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
