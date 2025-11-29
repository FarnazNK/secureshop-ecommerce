import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api } from '../utils/api';

interface UserProfile {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  phone?: string;
  avatar?: string;
  emailVerified: boolean;
  createdAt: string;
  lastLoginAt?: string;
}

export function AccountPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [formData, setFormData] = useState({
    firstName: '',
    lastName: '',
    phone: '',
  });

  useEffect(() => {
    if (!user) {
      navigate('/login?redirect=/account');
      return;
    }

    api.get('/users/profile')
      .then((res) => {
        const p = res.data.data.user;
        setProfile(p);
        setFormData({
          firstName: p.firstName || '',
          lastName: p.lastName || '',
          phone: p.phone || '',
        });
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [user, navigate]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      const res = await api.put('/users/profile', formData);
      setProfile(res.data.data.user);
      setEditing(false);
      setSuccess('Profile updated successfully');
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      setError(err.response?.data?.error?.message || 'Failed to update profile');
    } finally {
      setSaving(false);
    }
  };

  const handleLogout = async () => {
    await logout();
    navigate('/');
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-sand-50 flex items-center justify-center">
        <div className="animate-spin w-8 h-8 border-4 border-accent-600 border-t-transparent rounded-full" />
      </div>
    );
  }

  if (!profile) {
    return null;
  }

  const menuItems = [
    { label: 'Orders', href: '/orders', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2' },
    { label: 'Addresses', href: '/account/addresses', icon: 'M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z M15 11a3 3 0 11-6 0 3 3 0 016 0z' },
    { label: 'Wishlist', href: '/wishlist', icon: 'M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z' },
  ];

  return (
    <div className="min-h-screen bg-sand-50">
      {/* Header */}
      <div className="bg-ink-900 text-white py-16">
        <div className="container-page">
          <div className="flex items-center gap-6">
            <div className="w-20 h-20 bg-accent-600 rounded-full flex items-center justify-center text-2xl font-display font-bold">
              {profile.firstName[0]}{profile.lastName[0]}
            </div>
            <div>
              <h1 className="text-display-md font-display">
                {profile.firstName} {profile.lastName}
              </h1>
              <p className="text-ink-300">{profile.email}</p>
            </div>
          </div>
        </div>
      </div>

      <div className="container-page py-12">
        <div className="grid lg:grid-cols-4 gap-8">
          {/* Sidebar */}
          <aside className="lg:col-span-1">
            <nav className="bg-white rounded-xl shadow-sm border border-ink-100 overflow-hidden">
              {menuItems.map((item) => (
                <Link
                  key={item.href}
                  to={item.href}
                  className="flex items-center gap-3 px-6 py-4 text-ink-700 hover:bg-ink-50 hover:text-ink-900 transition-colors border-b border-ink-100 last:border-0"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={item.icon} />
                  </svg>
                  {item.label}
                </Link>
              ))}
              <button
                onClick={handleLogout}
                className="w-full flex items-center gap-3 px-6 py-4 text-red-600 hover:bg-red-50 transition-colors"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
                Sign Out
              </button>
            </nav>
          </aside>

          {/* Main Content */}
          <main className="lg:col-span-3 space-y-6">
            {/* Alerts */}
            {error && (
              <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
                {error}
              </div>
            )}
            {success && (
              <div className="p-4 bg-green-50 border border-green-200 rounded-lg text-green-700">
                {success}
              </div>
            )}

            {/* Profile Card */}
            <div className="bg-white rounded-xl shadow-sm border border-ink-100 p-6">
              <div className="flex justify-between items-start mb-6">
                <h2 className="font-display text-xl text-ink-900">Profile Information</h2>
                {!editing && (
                  <button
                    onClick={() => setEditing(true)}
                    className="text-accent-600 hover:text-accent-700 font-medium text-sm"
                  >
                    Edit
                  </button>
                )}
              </div>

              {editing ? (
                <form onSubmit={handleSave} className="space-y-4">
                  <div className="grid sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-ink-700 mb-1">
                        First Name
                      </label>
                      <input
                        type="text"
                        value={formData.firstName}
                        onChange={(e) => setFormData({ ...formData, firstName: e.target.value })}
                        className="w-full px-4 py-2 border border-ink-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-ink-700 mb-1">
                        Last Name
                      </label>
                      <input
                        type="text"
                        value={formData.lastName}
                        onChange={(e) => setFormData({ ...formData, lastName: e.target.value })}
                        className="w-full px-4 py-2 border border-ink-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-ink-700 mb-1">
                      Phone
                    </label>
                    <input
                      type="tel"
                      value={formData.phone}
                      onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                      className="w-full px-4 py-2 border border-ink-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-500"
                    />
                  </div>
                  <div className="flex gap-4 pt-4">
                    <button type="submit" disabled={saving} className="btn-primary">
                      {saving ? 'Saving...' : 'Save Changes'}
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setEditing(false);
                        setFormData({
                          firstName: profile.firstName,
                          lastName: profile.lastName,
                          phone: profile.phone || '',
                        });
                      }}
                      className="btn-secondary"
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              ) : (
                <dl className="grid sm:grid-cols-2 gap-6">
                  <div>
                    <dt className="text-sm text-ink-500">Full Name</dt>
                    <dd className="mt-1 text-ink-900 font-medium">
                      {profile.firstName} {profile.lastName}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-sm text-ink-500">Email</dt>
                    <dd className="mt-1 text-ink-900 font-medium flex items-center gap-2">
                      {profile.email}
                      {profile.emailVerified ? (
                        <span className="text-green-600 text-xs bg-green-50 px-2 py-0.5 rounded">
                          Verified
                        </span>
                      ) : (
                        <span className="text-amber-600 text-xs bg-amber-50 px-2 py-0.5 rounded">
                          Unverified
                        </span>
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-sm text-ink-500">Phone</dt>
                    <dd className="mt-1 text-ink-900 font-medium">
                      {profile.phone || 'Not provided'}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-sm text-ink-500">Member Since</dt>
                    <dd className="mt-1 text-ink-900 font-medium">
                      {new Date(profile.createdAt).toLocaleDateString('en-US', {
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric',
                      })}
                    </dd>
                  </div>
                </dl>
              )}
            </div>

            {/* Security Card */}
            <div className="bg-white rounded-xl shadow-sm border border-ink-100 p-6">
              <h2 className="font-display text-xl text-ink-900 mb-6">Security</h2>
              <div className="space-y-4">
                <div className="flex items-center justify-between py-3 border-b border-ink-100">
                  <div>
                    <p className="font-medium text-ink-900">Password</p>
                    <p className="text-sm text-ink-500">Last changed: Unknown</p>
                  </div>
                  <button className="text-accent-600 hover:text-accent-700 font-medium text-sm">
                    Change Password
                  </button>
                </div>
                <div className="flex items-center justify-between py-3">
                  <div>
                    <p className="font-medium text-ink-900">Two-Factor Authentication</p>
                    <p className="text-sm text-ink-500">Add an extra layer of security</p>
                  </div>
                  <button className="text-accent-600 hover:text-accent-700 font-medium text-sm">
                    Enable
                  </button>
                </div>
              </div>
            </div>

            {/* Danger Zone */}
            <div className="bg-white rounded-xl shadow-sm border border-red-200 p-6">
              <h2 className="font-display text-xl text-red-700 mb-4">Danger Zone</h2>
              <p className="text-ink-600 mb-4">
                Once you delete your account, there is no going back. Please be certain.
              </p>
              <button className="text-red-600 hover:text-red-700 font-medium text-sm border border-red-200 px-4 py-2 rounded-lg hover:bg-red-50 transition-colors">
                Delete Account
              </button>
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
