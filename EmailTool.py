from typing import Optional
from phi.tools import Toolkit
from phi.utils.log import logger

class EmailTools(Toolkit):
    def __init__(
        self,
        receiver_email: Optional[str] = None,
        sender_name: Optional[str] = None,
        sender_email: Optional[str] = None,
        sender_passkey: Optional[str] = None,
        email_user: bool = True,
        read_email_imap: bool = True,
        read_email_pop3: bool = True,
    ):
        super().__init__(name="email_tools")
        self.receiver_email: Optional[str] = receiver_email
        self.sender_name: Optional[str] = sender_name
        self.sender_email: Optional[str] = sender_email
        self.sender_passkey: Optional[str] = sender_passkey
        if email_user: 
            self.register(self.email_user)
        if read_email_imap:
            self.register(self.read_email_imap)
        if read_email_pop3:
            self.register(self.read_email_pop3)

    def email_user(self, subject: str, body: str) -> str:
        """use this function to send Emails to the user with the given subject and body.

        :param subject: The subject of the email.
        :param body: The body of the email.
        :return: "success" if the email was sent successfully, "error: [error message]" otherwise.
        """
        try:
            import smtplib
            from email.message import EmailMessage
        except ImportError:
            logger.error("`smtplib` not installed")
            raise

        if not self.receiver_email:
            return "error: No receiver email provided"
        if not self.sender_name:
            return "error: No sender name provided"
        if not self.sender_email:
            return "error: No sender email provided"
        if not self.sender_passkey:
            return "error: No sender passkey provided"

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"{self.sender_name} <{self.sender_email}>"
        msg["To"] = self.receiver_email
        msg.set_content(body)

        logger.info(f"Sending Email to {self.receiver_email}")
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                smtp.login(self.sender_email, self.sender_passkey)
                smtp.send_message(msg)
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return f"error: {e}"
        return "email sent successfully"
    

    def read_email_imap(self, folder: str = "inbox", search_criteria: str = "ALL") -> str:
        """Reads emails from the specified folder using IMAP and returns them in JSON format.

        :param folder: The folder to read emails from (default is "inbox").
        :param search_criteria: The search criteria for filtering emails (default is "ALL").
        :return: A JSON string summarizing the fetched emails or an error message.
        """
        try:
            import imaplib
            import email
            from email.header import decode_header
            import json
        except ImportError:
            logger.error("Required modules not installed")
            raise

        if not self.sender_email:
            logger.error("No email address provided")
            return json.dumps({"error": "No email address provided"})
        if not self.sender_passkey:
            logger.error("No passkey provided")
            return json.dumps({"error": "No passkey provided"})

        imap_server = "imap.gmail.com"

        try:
            logger.info("Connecting to IMAP server")
            mail = imaplib.IMAP4_SSL(imap_server)
            mail.login(self.sender_email, self.sender_passkey)
            logger.info(f"Logged in as {self.sender_email}")

            mail.select(folder)
            logger.info(f"Selected folder: {folder}")

            status, messages = mail.search(None, search_criteria)
            logger.info(f"Search status: {status}, messages: {messages}")

            if status != "OK":
                logger.error(f"Failed to search emails with criteria {search_criteria}")
                return json.dumps({"error": f"Failed to search emails with criteria {search_criteria}"})

            email_ids = messages[0].split()
            logger.info(f"Found {len(email_ids)} emails")

            if not email_ids:
                logger.info("No emails found")
                return json.dumps({"error": "No emails found"})

            emails = []
            for i, email_id in enumerate(reversed(email_ids[-4:])):
                # if i >= 4:  # Only process the first two emails
                #     break
                logger.info(f"Fetching email ID: {email_id.decode()}")
                status, msg_data = mail.fetch(email_id, "(RFC822)")
                logger.info(f"Fetch status: {status}")

                if status != "OK":
                    logger.error(f"Failed to fetch email ID {email_id.decode()}")
                    return json.dumps({"error": f"Failed to fetch email ID {email_id.decode()}"})

                msg = email.message_from_bytes(msg_data[0][1])
                subject, encoding = decode_header(msg["Subject"])[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding if encoding else "utf-8")
                
                # Get the email body
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        content_disposition = str(part.get("Content-Disposition"))

                        if "attachment" in content_disposition:
                            continue

                        if content_type == "text/plain" and "attachment" not in content_disposition:
                            body = part.get_payload(decode=True).decode()
                            break
                else:
                    body = msg.get_payload(decode=True).decode()

                logger.info(f"Email subject: {subject} and body: {body}")
                emails.append({"subject": subject, "body": body})

            mail.logout()
            logger.debug("Logged out from IMAP server")
            return json.dumps(emails)
        except Exception as e:
            logger.error(f"Error reading emails: {e}")
            return json.dumps({"error": str(e)})
        

    def read_email_pop3(self) -> str:
        """Reads emails from POP3 server and returns them in JSON format."""
        try:
            import poplib
            import email
            from email.header import decode_header
            import json

            if not self.sender_email:
                logger.error("No email address provided")
                return json.dumps({"error": "No email address provided"})
            if not self.sender_passkey:
                logger.error("No passkey provided")
                return json.dumps({"error": "No passkey provided"})

            pop_server = "pop.gmail.com"
            mail = poplib.POP3_SSL(pop_server)
            mail.user(self.sender_email)
            mail.pass_(self.sender_passkey)
            num_messages = len(mail.list()[1])
            logger.info(f"Number of messages in the mailbox: {num_messages}")

            emails = []
            for i in range(num_messages):
                raw_email = b"\n".join(mail.retr(i+1)[1])
                msg = email.message_from_bytes(raw_email)

                subject, encoding = decode_header(msg["Subject"])[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding if encoding else "utf-8")
                
                # Get the email body
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        content_disposition = str(part.get("Content-Disposition"))

                        if "attachment" in content_disposition:
                            continue

                        if content_type == "text/plain" and "attachment" not in content_disposition:
                            body = part.get_payload(decode=True).decode()
                            break
                else:
                    body = msg.get_payload(decode=True).decode()

                logger.info(f"Email subject: {subject} and body: {body}")
                emails.append({"subject": subject, "body": body})

            mail.quit()
            logger.debug("Logged out from POP3 server")
            return json.dumps(emails)
        except Exception as e:
            logger.error(f"Error reading emails: {e}")
            return json.dumps({"error": str(e)})

