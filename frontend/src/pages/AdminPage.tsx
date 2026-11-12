import React, { useMemo, useState } from 'react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import {
  Settings,
  Shield,
  Users,
  UserPlus,
  Search,
  CheckCircle,
  XCircle,
  RefreshCw,
} from 'lucide-react';
import {
  useUsers,
  useCreateUser,
  useUpdateUser,
} from '@/api/hooks';
import type { User, UserRole } from '@/api/schemas';

const roles: UserRole[] = ['admin', 'doctor', 'nurse', 'operator'];

const roleLabels: Record<UserRole, string> = {
  admin: 'Admin',
  doctor: 'Doctor',
  nurse: 'Nurse',
  operator: 'Operator',
};

export const AdminPage: React.FC = () => {
  const { data: users = [], isLoading, isError, error, refetch } = useUsers();
  const createUser = useCreateUser();
  const updateUser = useUpdateUser();

  const [search, setSearch] = useState('');
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [form, setForm] = useState({
    username: '',
    email: '',
    password: '',
    role: 'nurse' as UserRole,
  });
  const [successMessage, setSuccessMessage] = useState('');
  const [actionError, setActionError] = useState('');

  const activeUsers = users.filter((user) => user.is_active).length;
  const inactiveUsers = users.length - activeUsers;

  const filteredUsers = useMemo(() => {
    const term = search.toLowerCase().trim();

    if (!term) return users;

    return users.filter((user) =>
      [user.username, user.email, user.role]
        .some((value) => value.toLowerCase().includes(term))
    );
  }, [users, search]);

  const handleCreateUser = async (event: React.FormEvent) => {
    event.preventDefault();
    setActionError('');
    setSuccessMessage('');

    try {
      await createUser.mutateAsync(form);
      setForm({
        username: '',
        email: '',
        password: '',
        role: 'nurse',
      });
      setShowCreateForm(false);
      setSuccessMessage('User account created successfully.');
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to create user.');
    }
  };

  const handleRoleChange = async (user: User, role: UserRole) => {
    setActionError('');
    setSuccessMessage('');

    try {
      await updateUser.mutateAsync({
        userId: user.id,
        updates: { role },
      });
      setSuccessMessage(`Role updated for ${user.username}.`);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to update role.');
    }
  };

  const handleStatusChange = async (user: User) => {
    setActionError('');
    setSuccessMessage('');

    const nextStatus = !user.is_active;

    if (!nextStatus && !window.confirm(`Deactivate ${user.username}'s account?`)) {
      return;
    }

    try {
      await updateUser.mutateAsync({
        userId: user.id,
        updates: { is_active: nextStatus },
      });
      setSuccessMessage(
        `${user.username}'s account has been ${nextStatus ? 'activated' : 'deactivated'}.`
      );
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to update account status.');
    }
  };

  const mutationPending = updateUser.isPending;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Hospital Administration"
        description="Manage CareGrid user accounts, access roles, and account status."
        badge={
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-500/10 text-slate-700 dark:text-slate-300 border border-slate-500/20">
            <Settings className="w-3 h-3" />
            Administrative Portal
          </span>
        }
      />

      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-text-muted">Total Users</p>
                <p className="text-2xl font-bold text-text-primary">{users.length}</p>
              </div>
              <Users className="w-7 h-7 text-brand-primary" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-text-muted">Active Users</p>
                <p className="text-2xl font-bold text-emerald-600">{activeUsers}</p>
              </div>
              <CheckCircle className="w-7 h-7 text-emerald-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-text-muted">Inactive Users</p>
                <p className="text-2xl font-bold text-amber-600">{inactiveUsers}</p>
              </div>
              <XCircle className="w-7 h-7 text-amber-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* User management */}
      <Card>
        <CardHeader>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <CardTitle className="text-sm font-bold uppercase tracking-wider text-text-secondary flex items-center gap-2">
              <Shield className="w-4 h-4 text-brand-primary" />
              User Management
            </CardTitle>

            <Button
              size="sm"
              leftIcon={<UserPlus className="w-4 h-4" />}
              onClick={() => {
                setShowCreateForm(!showCreateForm);
                setActionError('');
                setSuccessMessage('');
              }}
            >
              {showCreateForm ? 'Cancel' : 'Create User'}
            </Button>
          </div>
        </CardHeader>

        <CardContent>
          {/* Feedback */}
          {successMessage && (
            <div className="mb-4 rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-3 text-sm text-emerald-700 dark:text-emerald-400">
              {successMessage}
            </div>
          )}

          {actionError && (
            <div className="mb-4 rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-600">
              {actionError}
            </div>
          )}

          {/* Create user form */}
          {showCreateForm && (
            <form
              onSubmit={handleCreateUser}
              className="mb-6 rounded-xl border border-border-light bg-bg-surface p-4 space-y-4"
            >
              <h3 className="text-sm font-semibold text-text-primary">
                Create New Account
              </h3>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <label className="space-y-1 text-xs text-text-secondary">
                  Username
                  <input
                    required
                    minLength={3}
                    maxLength={50}
                    value={form.username}
                    onChange={(e) => setForm({ ...form, username: e.target.value })}
                    className="w-full rounded-lg border border-border-light bg-bg-page px-3 py-2 text-sm text-text-primary"
                    placeholder="Enter username"
                  />
                </label>

                <label className="space-y-1 text-xs text-text-secondary">
                  Email
                  <input
                    required
                    type="email"
                    value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                    className="w-full rounded-lg border border-border-light bg-bg-page px-3 py-2 text-sm text-text-primary"
                    placeholder="Enter email"
                  />
                </label>

                <label className="space-y-1 text-xs text-text-secondary">
                  Password
                  <input
                    required
                    type="password"
                    minLength={8}
                    maxLength={72}
                    value={form.password}
                    onChange={(e) => setForm({ ...form, password: e.target.value })}
                    className="w-full rounded-lg border border-border-light bg-bg-page px-3 py-2 text-sm text-text-primary"
                    placeholder="Minimum 8 characters"
                  />
                </label>

                <label className="space-y-1 text-xs text-text-secondary">
                  Role
                  <select
                    value={form.role}
                    onChange={(e) =>
                      setForm({ ...form, role: e.target.value as UserRole })
                    }
                    className="w-full rounded-lg border border-border-light bg-bg-page px-3 py-2 text-sm text-text-primary"
                  >
                    {roles.map((role) => (
                      <option key={role} value={role}>
                        {roleLabels[role]}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <Button type="submit" disabled={createUser.isPending}>
                {createUser.isPending ? 'Creating...' : 'Create Account'}
              </Button>
            </form>
          )}

          {/* Search and refresh */}
          <div className="flex flex-col sm:flex-row gap-3 mb-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search username, email, or role..."
                className="w-full rounded-lg border border-border-light bg-bg-page pl-9 pr-3 py-2 text-sm text-text-primary"
              />
            </div>

            <Button
              variant="outline"
              size="sm"
              leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
              onClick={() => void refetch()}
            >
              Refresh
            </Button>
          </div>

          {/* User table */}
          {isLoading ? (
            <p className="py-8 text-center text-sm text-text-muted">
              Loading users...
            </p>
          ) : isError ? (
            <div className="py-8 text-center space-y-3">
              <p className="text-sm text-red-500">
                {error instanceof Error ? error.message : 'Unable to load users.'}
              </p>
              <Button variant="outline" size="sm" onClick={() => void refetch()}>
                Retry
              </Button>
            </div>
          ) : filteredUsers.length === 0 ? (
            <p className="py-8 text-center text-sm text-text-muted">
              No users found.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-border-light text-text-muted">
                    <th className="py-3 pr-4 font-semibold">User</th>
                    <th className="py-3 px-4 font-semibold">Role</th>
                    <th className="py-3 px-4 font-semibold">Status</th>
                    <th className="py-3 pl-4 font-semibold">Action</th>
                  </tr>
                </thead>

                <tbody>
                  {filteredUsers.map((user) => (
                    <tr key={user.id} className="border-b border-border-light last:border-0">
                      <td className="py-3 pr-4">
                        <p className="font-semibold text-text-primary">{user.username}</p>
                        <p className="text-text-muted mt-1">{user.email}</p>
                      </td>

                      <td className="py-3 px-4">
                        <select
                          value={user.role}
                          disabled={mutationPending}
                          onChange={(e) =>
                            void handleRoleChange(user, e.target.value as UserRole)
                          }
                          className="rounded-md border border-border-light bg-bg-page px-2 py-1.5 text-text-primary disabled:opacity-50"
                        >
                          {roles.map((role) => (
                            <option key={role} value={role}>
                              {roleLabels[role]}
                            </option>
                          ))}
                        </select>
                      </td>

                      <td className="py-3 px-4">
                        <span
                          className={`inline-flex items-center gap-1 rounded-full px-2 py-1 font-semibold ${
                            user.is_active
                              ? 'bg-emerald-500/10 text-emerald-600'
                              : 'bg-amber-500/10 text-amber-600'
                          }`}
                        >
                          {user.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>

                      <td className="py-3 pl-4">
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={mutationPending}
                          onClick={() => void handleStatusChange(user)}
                        >
                          {user.is_active ? 'Deactivate' : 'Activate'}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
