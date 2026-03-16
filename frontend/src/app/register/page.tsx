'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';
import { register as apiRegister, getMe } from '@/lib/api';
import { useAuthStore } from '@/lib/auth-store';

export default function RegisterPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [tenantName, setTenantName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const { setAuth } = useAuthStore();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const { access_token } = await apiRegister(email, password, tenantName || 'Meine Firma', displayName);
      localStorage.setItem('token', access_token);
      const user = await getMe();
      setAuth(access_token, user);
      router.push('/dashboard');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Registrierung fehlgeschlagen');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <h1 className="text-xl font-bold">📗 RDS Buchhaltung</h1>
          <p className="text-sm text-gray-500">Neues Konto erstellen</p>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <Input placeholder="Firmenname" value={tenantName} onChange={(e) => setTenantName(e.target.value)} />
            <Input placeholder="Ihr Name" value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
            <Input type="email" placeholder="E-Mail" value={email} onChange={(e) => setEmail(e.target.value)} required />
            <Input type="password" placeholder="Passwort (min. 8 Zeichen)" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} />
            {error && <p className="text-sm text-red-500">{error}</p>}
            <Button type="submit" className="w-full" disabled={loading}>{loading ? 'Laden...' : 'Registrieren'}</Button>
          </form>
          <p className="text-center text-sm text-gray-500 mt-4">
            Bereits registriert? <a href="/login" className="text-brand-600 hover:underline">Anmelden</a>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
