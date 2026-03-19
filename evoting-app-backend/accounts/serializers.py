from datetime import date

from django.contrib.auth import get_user_model
from rest_framework import serializers

from accounts.models import VoterProfile
from elections.models import VotingStation

User = get_user_model()


# ==============================
# USER SERIALIZER
# ==============================
class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "first_name", "last_name",
            "full_name", "role", "is_active", "is_verified",
            "date_joined", "password"
        ]
        read_only_fields = ["id", "date_joined"]

    def get_full_name(self, obj):
        return f"{obj.first_name or ''} {obj.last_name or ''}".strip()


# ==============================
# VOTER PROFILE SERIALIZER
# ==============================
class VoterProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    age = serializers.ReadOnlyField()
    station_name = serializers.CharField(source="station.name", read_only=True)

    class Meta:
        model = VoterProfile
        fields = [
            "id", "user", "national_id", "voter_card_number",
            "date_of_birth", "age", "gender", "address",
            "phone", "station", "station_name",
        ]
        read_only_fields = ["id"]


# ==============================
# LOGIN SERIALIZERS
# ==============================
class AdminLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class VoterLoginSerializer(serializers.Serializer):
    voter_card_number = serializers.CharField(max_length=12)
    password = serializers.CharField(write_only=True)


# ==============================
# VOTER REGISTRATION
# ==============================
class VoterRegistrationSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=200)
    national_id = serializers.CharField(max_length=50)
    date_of_birth = serializers.DateField()
    gender = serializers.ChoiceField(choices=VoterProfile.Gender.choices)
    address = serializers.CharField()
    phone = serializers.CharField(max_length=20)
    email = serializers.EmailField()
    station_id = serializers.IntegerField()
    password = serializers.CharField(min_length=6, write_only=True)
    confirm_password = serializers.CharField(min_length=6, write_only=True)

    # -------- VALIDATIONS --------
    def validate_national_id(self, value):
        if VoterProfile.objects.filter(national_id=value).exists():
            raise serializers.ValidationError("A voter with this National ID already exists.")
        return value

    def validate_date_of_birth(self, value):
        today = date.today()
        age = today.year - value.year - (
            (today.month, today.day) < (value.month, value.day)
        )
        if age < 18:
            raise serializers.ValidationError("You must be at least 18 years old.")
        return value

    def validate_station_id(self, value):
        if not VotingStation.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Invalid voting station.")
        return value

    def validate(self, data):
        if data["password"] != data["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )
        return data

    # -------- CREATE USER --------
    def create(self, validated_data):
        validated_data.pop("confirm_password")

        full_name = validated_data["full_name"].split(" ", 1)
        first_name = full_name[0]
        last_name = full_name[1] if len(full_name) > 1 else ""

        user = User.objects.create_user(
            username=validated_data["national_id"],
            email=validated_data["email"],
            first_name=first_name,
            last_name=last_name,
            password=validated_data["password"],
            role=User.Role.VOTER
        )

        # Simple voter card generator (you can improve this)
        voter_card_number = f"VC{user.id:06d}"

        VoterProfile.objects.create(
            user=user,
            national_id=validated_data["national_id"],
            voter_card_number=voter_card_number,
            date_of_birth=validated_data["date_of_birth"],
            gender=validated_data["gender"],
            address=validated_data["address"],
            phone=validated_data["phone"],
            station_id=validated_data["station_id"],
        )

        return user


# ==============================
# ADMIN CREATE
# ==============================
class AdminCreateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    full_name = serializers.CharField(max_length=200)
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=[
        User.Role.SUPER_ADMIN,
        User.Role.ELECTION_OFFICER,
        User.Role.STATION_MANAGER,
        User.Role.AUDITOR,
        User.Role.VOTER,
    ])
    password = serializers.CharField(min_length=6, write_only=True)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already exists.")
        return value

    def create(self, validated_data):
        full_name = validated_data["full_name"].split(" ", 1)
        first_name = full_name[0]
        last_name = full_name[1] if len(full_name) > 1 else ""

        return User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            first_name=first_name,
            last_name=last_name,
            password=validated_data["password"],
            role=validated_data["role"]
        )


# ==============================
# CHANGE PASSWORD
# ==============================
class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(min_length=6, write_only=True)
    confirm_password = serializers.CharField(min_length=6, write_only=True)

    def validate(self, data):
        if data["new_password"] != data["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )
        return data


# ==============================
# LIST SERIALIZERS
# ==============================
class VoterListSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    voter_card_number = serializers.CharField(source="voter_profile.voter_card_number")
    station_id = serializers.IntegerField(source="voter_profile.station_id")
    age = serializers.ReadOnlyField(source="voter_profile.age")
    gender = serializers.CharField(source="voter_profile.gender")
    national_id = serializers.CharField(source="voter_profile.national_id")

    class Meta:
        model = User
        fields = [
            "id", "full_name", "voter_card_number", "national_id",
            "station_id", "age", "gender", "is_verified", "is_active",
        ]

    def get_full_name(self, obj):
        return obj.get_full_name()


class AdminListSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "username", "full_name", "email",
            "role", "is_active", "date_joined"
        ]

    def get_full_name(self, obj):
        return f"{obj.first_name or ''} {obj.last_name or ''}".strip()