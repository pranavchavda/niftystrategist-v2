import React, { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router';
import { User, Mail, Text, Save, ArrowLeft, Loader2 } from 'lucide-react';
import { Button } from '../components/catalyst/button';
import { Input } from '../components/catalyst/input';
import { Link } from 'react-router';

interface AuthContextType {
  user: any;
  setUser: (user: any) => void;
  authToken: string | null;
  setAuthToken: (token: string | null) => void;
  logout: () => void;
}

interface UserProfile {
  id: number;
  email: string;
  name: string;
  bio?: string;
  picture?: string;
}

export default function UserProfile() {
  const context = useOutletContext();
  console.log('UserProfile context:', context);
  
  const { user, setUser, authToken } = context || {};
  
  if (!authToken) {
    console.error('No authToken found in context');
    return <div>Authentication required</div>;
  }
  const [profile, setProfile] = useState<UserProfile>({
    id: user?.id || 0,
    email: user?.email || '',
    name: user?.name || '',
    bio: user?.bio || '',
    picture: user?.picture || ''
  });
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Load current user data
  useEffect(() => {
    if (!authToken) return;

    const loadProfile = async () => {
      try {
        setLoading(true);
        const response = await fetch('/api/auth/me', {
          headers: {
            'Authorization': `Bearer ${authToken}`
          }
        });

        if (response.ok) {
          const userData = await response.json();
          setProfile({
            id: userData.id,
            email: userData.email,
            name: userData.name || '',
            bio: userData.bio || '',
            picture: userData.picture || ''
          });
        } else {
          setMessage({ type: 'error', text: 'Failed to load profile data' });
        }
      } catch (error) {
        console.error('Failed to load profile:', error);
        setMessage({ type: 'error', text: 'Error loading profile data' });
      } finally {
        setLoading(false);
      }
    };

    loadProfile();
  }, [authToken]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!authToken) {
      setMessage({ type: 'error', text: 'Not authenticated' });
      return;
    }

    try {
      setSaving(true);
      setMessage(null);

      const response = await fetch('/api/user/profile', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          name: profile.name,
          email: profile.email,
          bio: profile.bio
        })
      });

      if (response.ok) {
        const updatedUser = await response.json();
        
        // Update global user state
        if (setUser) {
          setUser(updatedUser);
        }

        // Update local state
        setProfile({
          id: updatedUser.id,
          email: updatedUser.email,
          name: updatedUser.name || '',
          bio: updatedUser.bio || '',
          picture: updatedUser.picture || ''
        });

        setMessage({ type: 'success', text: 'Profile updated successfully!' });
        
        // Clear success message after 3 seconds
        setTimeout(() => setMessage(null), 3000);
      } else {
        const errorData = await response.json();
        setMessage({ 
          type: 'error', 
          text: errorData.detail || 'Failed to update profile' 
        });
      }
    } catch (error) {
      console.error('Failed to update profile:', error);
      setMessage({ type: 'error', text: 'Error updating profile' });
    } finally {
      setSaving(false);
    }
  };

  const handleInputChange = (field: keyof UserProfile) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    setProfile(prev => ({
      ...prev,
      [field]: e.target.value
    }));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex items-center gap-3 text-zinc-500">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span>Loading profile...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center gap-4 mb-8">
        <Link to="/settings">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Settings
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
            User Profile
          </h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
            Manage your personal information and preferences
          </p>
        </div>
      </div>

      {/* Message */}
      {message && (
        <div className={`mb-6 p-4 rounded-lg ${
          message.type === 'success' 
            ? 'bg-green-50 dark:bg-green-900/20 text-green-800 dark:text-green-200 border border-green-200 dark:border-green-800'
            : 'bg-red-50 dark:bg-red-900/20 text-red-800 dark:text-red-200 border border-red-200 dark:border-red-800'
        }`}>
          {message.text}
        </div>
      )}

      {/* Profile Form */}
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Profile Picture Section */}
        <div className="bg-white dark:bg-zinc-900 rounded-xl p-6 shadow-sm border border-zinc-200 dark:border-zinc-800">
          <div className="flex items-center gap-6">
            <div className="relative">
              <div className="w-20 h-20 rounded-full bg-gradient-to-br from-amber-500 via-orange-500 to-red-500 flex items-center justify-center text-white text-2xl font-bold shadow-lg">
                {profile.name?.charAt(0)?.toUpperCase() || profile.email?.charAt(0)?.toUpperCase() || 'U'}
              </div>
              {profile.picture && (
                <img
                  src={profile.picture}
                  alt="Profile"
                  className="absolute inset-0 w-20 h-20 rounded-full object-cover"
                />
              )}
            </div>
            <div>
              <h3 className="font-semibold text-zinc-900 dark:text-zinc-100">Profile Picture</h3>
              <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
                Your profile picture is managed through your Google account
              </p>
            </div>
          </div>
        </div>

        {/* Basic Information */}
        <div className="bg-white dark:bg-zinc-900 rounded-xl p-6 shadow-sm border border-zinc-200 dark:border-zinc-800">
          <div className="flex items-center gap-2 mb-6">
            <User className="w-5 h-5 text-zinc-500" />
            <h3 className="font-semibold text-zinc-900 dark:text-zinc-100">Basic Information</h3>
          </div>

          <div className="space-y-4">
            {/* Name */}
            <div>
              <label htmlFor="name" className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                Name
              </label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
                <Input
                  id="name"
                  type="text"
                  value={profile.name}
                  onChange={handleInputChange('name')}
                  placeholder="Enter your name"
                  className="pl-10"
                  required
                />
              </div>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                This is how you'll be addressed in conversations
              </p>
            </div>

            {/* Email */}
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                Email Address
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
                <Input
                  id="email"
                  type="email"
                  value={profile.email}
                  onChange={handleInputChange('email')}
                  placeholder="Enter your email"
                  className="pl-10"
                  required
                />
              </div>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                Your login email and contact address
              </p>
            </div>

            {/* Bio */}
            <div>
              <label htmlFor="bio" className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                Bio
              </label>
              <div className="relative">
                <Text className="absolute left-3 top-3 w-4 h-4 text-zinc-400" />
                <textarea
                  id="bio"
                  value={profile.bio}
                  onChange={handleInputChange('bio')}
                  placeholder="Tell us about yourself, your role, and any preferences..."
                  className="w-full px-3 py-2 pl-10 min-h-[100px] rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 placeholder-zinc-500 dark:placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-zinc-300 dark:focus:ring-zinc-600 focus:border-transparent"
                  rows={4}
                />
              </div>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                Share information about yourself to help personalize your experience
              </p>
            </div>
          </div>
        </div>

        {/* Submit Button */}
        <div className="flex justify-end gap-3">
          <Link to="/settings">
            <Button variant="ghost">
              Cancel
            </Button>
          </Link>
          <Button
            type="submit"
            disabled={saving}
            className="min-w-[120px]"
          >
            {saving ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="w-4 h-4 mr-2" />
                Save Changes
              </>
            )}
          </Button>
        </div>
      </form>

      {/* Divider */}
      <div className="my-8 border-t border-zinc-200 dark:border-zinc-800" />

      {/* Additional Information */}
      <div className="bg-zinc-50 dark:bg-zinc-800/50 rounded-xl p-6 border border-zinc-200 dark:border-zinc-700">
        <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 mb-4">About Your Profile</h3>
        <div className="space-y-3 text-sm text-zinc-600 dark:text-zinc-400">
          <p>
            <strong>Personalization:</strong> Your profile information helps Nifty Strategist provide more relevant and personalized responses based on your background and preferences.
          </p>
          <p>
            <strong>Context:</strong> Your name and bio are included in conversation context to help the AI understand who you are and tailor responses accordingly.
          </p>
          <p>
            <strong>Privacy:</strong> Your information is used only for personalization purposes and is never shared with third parties.
          </p>
        </div>
      </div>
    </div>
  );
}
