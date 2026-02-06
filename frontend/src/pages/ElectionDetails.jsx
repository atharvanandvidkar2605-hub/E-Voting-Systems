import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../utils/AuthContext';
import { electionsAPI } from '../utils/api';
import {
    Vote, Calendar, Clock, Users, ArrowLeft, User,
    CheckCircle, AlertCircle, Timer, XCircle, Info
} from 'lucide-react';
import toast from 'react-hot-toast';
import Loading from '../components/Loading';

const ElectionDetails = () => {
    const { id } = useParams();
    const navigate = useNavigate();
    const { user, isAuthenticated } = useAuth();

    const [election, setElection] = useState(null);
    const [loading, setLoading] = useState(true);
    const [hasVoted, setHasVoted] = useState(false);

    useEffect(() => {
        fetchElectionData();
    }, [id]);

    const fetchElectionData = async () => {
        try {
            const response = await electionsAPI.getOne(id);
            setElection(response.data.election);

            // Check if user has voted
            if (isAuthenticated) {
                try {
                    const votedRes = await electionsAPI.hasVoted(id);
                    setHasVoted(votedRes.data.has_voted);
                } catch (err) {
                    setHasVoted(false);
                }
            }
        } catch (error) {
            console.error('Error fetching election:', error);
            toast.error('Failed to load election details');
            navigate('/elections');
        } finally {
            setLoading(false);
        }
    };

    const getElectionStatus = () => {
        if (!election) return null;

        const now = new Date();
        const startTime = new Date(election.start_time);
        const endTime = new Date(election.end_time);

        if (!election.is_active) {
            return { label: 'Inactive', color: 'bg-red-100 text-red-700', icon: XCircle };
        }
        if (now < startTime) {
            return { label: 'Upcoming', color: 'bg-blue-100 text-blue-700', icon: Timer };
        }
        if (now > endTime) {
            return { label: 'Ended', color: 'bg-yellow-100 text-yellow-700', icon: CheckCircle };
        }
        return { label: 'Active - Voting Open', color: 'bg-green-100 text-green-700', icon: Vote };
    };

    const formatDate = (dateString) => {
        return new Date(dateString).toLocaleDateString('en-IN', {
            day: 'numeric',
            month: 'long',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    const canVote = () => {
        if (!election || !isAuthenticated || !user?.is_verified) return false;

        const now = new Date();
        const startTime = new Date(election.start_time);
        const endTime = new Date(election.end_time);

        return election.is_active &&
            now >= startTime &&
            now <= endTime &&
            !hasVoted;
    };

    if (loading) {
        return <Loading message="Loading election details..." />;
    }

    if (!election) {
        return (
            <div className="min-h-screen bg-gray-50 flex items-center justify-center">
                <div className="text-center">
                    <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
                    <h2 className="text-2xl font-bold text-gray-900">Election Not Found</h2>
                    <button
                        onClick={() => navigate('/elections')}
                        className="mt-4 btn-primary"
                    >
                        Back to Elections
                    </button>
                </div>
            </div>
        );
    }

    const status = getElectionStatus();
    const StatusIcon = status?.icon;
    const candidates = election.candidates || [];

    return (
        <div className="min-h-screen bg-gray-50 py-8">
            <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
                {/* Back Button */}
                <button
                    onClick={() => navigate('/elections')}
                    className="flex items-center space-x-2 text-gray-600 hover:text-gray-900 mb-6 transition-colors"
                >
                    <ArrowLeft className="w-5 h-5" />
                    <span>Back to Elections</span>
                </button>

                {/* Election Header */}
                <div className="bg-white rounded-2xl shadow-sm p-6 mb-6">
                    <div className="flex items-start justify-between">
                        <div className="flex-1">
                            <div className="flex items-center space-x-3 mb-3">
                                <span className={`px-3 py-1 rounded-full text-sm font-medium flex items-center space-x-1 ${status?.color}`}>
                                    {StatusIcon && <StatusIcon className="w-4 h-4" />}
                                    <span>{status?.label}</span>
                                </span>
                                {hasVoted && (
                                    <span className="px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-700 flex items-center space-x-1">
                                        <CheckCircle className="w-4 h-4" />
                                        <span>You Voted</span>
                                    </span>
                                )}
                            </div>
                            <h1 className="text-3xl font-bold text-gray-900">{election.name}</h1>
                            {election.description && (
                                <p className="text-gray-600 mt-3 text-lg">{election.description}</p>
                            )}
                        </div>
                        <div className="w-16 h-16 bg-primary-100 rounded-xl flex items-center justify-center ml-4">
                            <Vote className="w-8 h-8 text-primary-600" />
                        </div>
                    </div>

                    <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div className="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
                            <Calendar className="w-5 h-5 text-gray-400" />
                            <div>
                                <p className="text-xs text-gray-500">Start Time</p>
                                <p className="text-sm font-medium text-gray-900">{formatDate(election.start_time)}</p>
                            </div>
                        </div>
                        <div className="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
                            <Clock className="w-5 h-5 text-gray-400" />
                            <div>
                                <p className="text-xs text-gray-500">End Time</p>
                                <p className="text-sm font-medium text-gray-900">{formatDate(election.end_time)}</p>
                            </div>
                        </div>
                        <div className="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
                            <Users className="w-5 h-5 text-gray-400" />
                            <div>
                                <p className="text-xs text-gray-500">Candidates</p>
                                <p className="text-sm font-medium text-gray-900">{candidates.length} Registered</p>
                            </div>
                        </div>
                    </div>

                    {/* Vote Button */}
                    {canVote() && (
                        <Link
                            to={`/elections/${election.id}/vote`}
                            className="mt-6 w-full flex items-center justify-center space-x-2 py-4 bg-primary-600 text-white rounded-xl font-semibold hover:bg-primary-700 transition-colors"
                        >
                            <Vote className="w-5 h-5" />
                            <span>Cast Your Vote Now</span>
                        </Link>
                    )}
                </div>

                {/* Candidates Section */}
                <div className="bg-white rounded-2xl shadow-sm p-6">
                    <div className="flex items-center space-x-3 mb-6">
                        <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
                            <Users className="w-5 h-5 text-purple-600" />
                        </div>
                        <div>
                            <h2 className="text-xl font-bold text-gray-900">Candidates</h2>
                            <p className="text-sm text-gray-500">Meet the candidates running in this election</p>
                        </div>
                    </div>

                    {candidates.length === 0 ? (
                        <div className="text-center py-12">
                            <User className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                            <h3 className="text-lg font-medium text-gray-900">No Candidates Yet</h3>
                            <p className="text-gray-500 mt-2">
                                Candidates haven't been added to this election yet.
                            </p>
                        </div>
                    ) : (
                        <div className="grid gap-4">
                            {candidates.map((candidate, index) => (
                                <div
                                    key={candidate.id}
                                    className="p-5 border border-gray-200 rounded-xl hover:border-primary-300 hover:bg-primary-50/30 transition-all"
                                >
                                    <div className="flex items-start space-x-4">
                                        <div className="w-14 h-14 bg-gradient-to-br from-primary-400 to-primary-600 rounded-full flex items-center justify-center text-white font-bold text-xl flex-shrink-0">
                                            {candidate.name.charAt(0).toUpperCase()}
                                        </div>
                                        <div className="flex-1">
                                            <div className="flex items-center space-x-2">
                                                <h3 className="text-lg font-semibold text-gray-900">{candidate.name}</h3>
                                                <span className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded-full">
                                                    #{index + 1}
                                                </span>
                                            </div>
                                            {candidate.party && (
                                                <p className="text-primary-600 font-medium mt-1">
                                                    {candidate.party}
                                                </p>
                                            )}
                                            {candidate.description ? (
                                                <div className="mt-3 p-3 bg-gray-50 rounded-lg">
                                                    <div className="flex items-start space-x-2">
                                                        <Info className="w-4 h-4 text-gray-400 flex-shrink-0 mt-0.5" />
                                                        <p className="text-gray-700 text-sm leading-relaxed">
                                                            {candidate.description}
                                                        </p>
                                                    </div>
                                                </div>
                                            ) : (
                                                <p className="text-gray-400 text-sm mt-2 italic">
                                                    No description provided
                                                </p>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Not Authenticated Banner */}
                {!isAuthenticated && (
                    <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-xl flex items-start space-x-3">
                        <AlertCircle className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
                        <div>
                            <h3 className="font-medium text-blue-900">Want to Vote?</h3>
                            <p className="text-sm text-blue-700 mt-1">
                                <Link to="/login" className="underline font-medium">Login</Link> or{' '}
                                <Link to="/register" className="underline font-medium">Register</Link>{' '}
                                to participate in this election.
                            </p>
                        </div>
                    </div>
                )}

                {/* Not Verified Banner */}
                {isAuthenticated && !user?.is_verified && (
                    <div className="mt-6 p-4 bg-yellow-50 border border-yellow-200 rounded-xl flex items-start space-x-3">
                        <AlertCircle className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
                        <div>
                            <h3 className="font-medium text-yellow-800">Account Not Verified</h3>
                            <p className="text-sm text-yellow-700 mt-1">
                                Your account needs admin verification before you can vote.
                                Please ensure you have provided a valid ID in your profile.
                            </p>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default ElectionDetails;
