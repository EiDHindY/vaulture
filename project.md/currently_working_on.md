Account Management
 ├─ create_account
____________________________________________________________________________________________________________
*narrative flow*
________________
    Use-case: create_account
    Primary actor: User
    Pre-condition: No user session exists on this device.
    Goal: Register a new account with a unique username, a strong master password (stored as an Argon2id hash)

* Trigger
User presses Register after filling the sign-up form.

* Main flow (happy path)

    1- System validates that the supplied username is not already taken after stripping it and converting it to lowercase.

    2- If the user chooses Generate, a random high-entropy password is shown; 
      otherwise the password entered is continuously evaluated against the policy 
      (length ≥ 12, upper/lower/digit/symbol entropy score ≥ 4).

    3- When the password meets the policy, system derives an Argon2id hash:
    4- System clears the GUI password field immediately after reading the value into volatile memory. 
    5- System writes a new user row:
      (user_id, username, password_hash, salt) - the username is saved after stripping it and converting it to lowercase
    6- the user is required to enter an email for recovery incase of forgetting the master_password
       Upon successful OTP entry, system stores the verified e-mail (user_id, username, password_hash, salt,rec_email)
    7- the user is required to enter a mobile number for recovery incase of forgetting the master_password
        Upon successful OTP entry, system stores the verified mobile number (user_id, username, password_hash, salt,rec_email,rec_mobile_number)

    8- System starts a logged-in session and navigates to the next page or window.

*Alternate flows
    1- Username taken: system shows error and restarts at step 1.
    2- Password too weak: strength meter remains red; user must revise.
    3- OTP timeout or failure: the system shows a resend option for the otp and won't proceed till both email and mobile_number are verified

* Post-conditions
    1- A new user record exists with (id,hashed password, salt,email,mobile_number).
    2- Audit log entry recorded: (event="UserCreated", user_id, timestamp,machine_ip).
    3- User is authenticated; inactivity timer starts for auto-lock.




*code flow*
________________
