import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Tooltip } from '@/components/ui/Tooltip';
import { Lock, ShieldCheck, ArrowLeft, KeyRound } from 'lucide-react';

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const authEnabled = import.meta.env.VITE_AUTH_ENABLED === 'true';

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
          {!authEnabled ? (
            <div className="space-y-4">
              <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-xs space-y-2">
                <div className="flex items-center gap-2 font-bold text-emerald-800 dark:text-emerald-300">
                  <ShieldCheck className="w-4 h-4 text-emerald-600" />
                  <span>Open Access Clinical Environment</span>
                </div>
                <p className="text-text-secondary leading-relaxed">
                  Authentication is currently bypassed (<code>VITE_AUTH_ENABLED=false</code>). All operational views, queue triage, and bed recommendation capabilities are open for authorized staff within the hospital intranet.
                </p>
              </div>

              <Button
                variant="primary"
                className="w-full"
                onClick={() => navigate('/')}
                leftIcon={<ArrowLeft className="w-4 h-4" />}
              >
                Enter Hospital Command Centre
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-xs text-amber-800 dark:text-amber-300">
                <strong>Backend Notice:</strong> Authentication endpoints (OAuth / JWT session exchange) are not implemented in the backend API.
              </div>

              <div className="space-y-3">
                <div className="space-y-1 text-xs">
                  <label className="text-text-muted font-medium">Clinician Badge ID</label>
                  <Input placeholder="CLIN-XXXXX" disabled leftIcon={<KeyRound className="w-3.5 h-3.5 text-text-muted" />} />
                </div>
                <div className="space-y-1 text-xs">
                  <label className="text-text-muted font-medium">Security Credential</label>
                  <Input type="password" placeholder="••••••••••••" disabled leftIcon={<Lock className="w-3.5 h-3.5 text-text-muted" />} />
                </div>
              </div>

              <Tooltip content="Authentication endpoints not implemented in backend">
                <div className="w-full">
                  <Button variant="primary" className="w-full" disabled>
                    Sign In
                  </Button>
                </div>
              </Tooltip>

              <Button
                variant="ghost"
                className="w-full text-xs"
                onClick={() => navigate('/')}
                leftIcon={<ArrowLeft className="w-3.5 h-3.5" />}
              >
                Return to Dashboard
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
