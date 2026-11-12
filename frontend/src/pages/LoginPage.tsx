import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Lock, ShieldCheck, KeyRound } from 'lucide-react';
import { useAuth } from '@/auth/AuthContext';
import { ApiRequestError } from '@/api/client';

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const { login } = useAuth();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    setError('');
    setIsSubmitting(true);

    try {
      await login(username.trim(), password);
      navigate('/', { replace: true });
    } catch (err) {
      if (err instanceof ApiRequestError) {
        setError(
          err.status === 401
            ? 'Invalid username or password.'
            : err.message
        );
      } else {
        setError('Unable to sign in. Please check your connection and try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen w-screen flex items-center justify-center bg-bg-page p-6 text-text-primary">
      <Card className="max-w-md w-full shadow-modal border-border-light">
        <CardHeader className="text-center pb-2">
          <div className="w-12 h-12 rounded-xl bg-brand-primary/10 text-brand-primary flex items-center justify-center mx-auto mb-3">
            <Lock className="w-6 h-6" />
          </div>

          <CardTitle className="text-lg font-bold">
            CareGrid Clinician Authentication
          </CardTitle>

          <p className="text-xs text-text-muted mt-1">
            St. Jude Central Hospital HMIS Access Gateway
          </p>
        </CardHeader>

        <CardContent className="space-y-5">
          <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-xs space-y-2">
            <div className="flex items-center gap-2 font-bold text-emerald-800 dark:text-emerald-300">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              <span>Secure Clinical Access</span>
            </div>

            <p className="text-text-secondary leading-relaxed">
              Sign in using your authorized CareGrid account credentials.
              Access is determined by your assigned role.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1 text-xs">
              <label className="text-text-muted font-medium">
                Username
              </label>

              <Input
                placeholder="Enter your username"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                leftIcon={
                  <KeyRound className="w-3.5 h-3.5 text-text-muted" />
                }
                disabled={isSubmitting}
              />
            </div>

            <div className="space-y-1 text-xs">
              <label className="text-text-muted font-medium">
                Password
              </label>

              <Input
                type="password"
                placeholder="Enter your password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                leftIcon={
                  <Lock className="w-3.5 h-3.5 text-text-muted" />
                }
                disabled={isSubmitting}
              />
            </div>

            {error && (
              <div
                role="alert"
                className="p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-xs text-red-700 dark:text-red-300"
              >
                {error}
              </div>
            )}

            <Button
              type="submit"
              variant="primary"
              className="w-full"
              disabled={
                isSubmitting ||
                !username.trim() ||
                !password
              }
            >
              {isSubmitting ? 'Signing In...' : 'Sign In'}
            </Button>
          </form>

          <p className="text-center text-xs text-text-muted">
            Account access is managed by the hospital administrator.
          </p>
        </CardContent>
      </Card>
    </div>
  );
};